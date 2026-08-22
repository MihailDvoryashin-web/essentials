from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from PIL import Image
from solders.pubkey import Pubkey

from .models import Token

logger = logging.getLogger(__name__)

METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
PUMPFUN_COIN_URL = "https://frontend-api-v3.pump.fun/coins-v2/{mint}"
MAX_IMAGE_BYTES = 10_000_000
MAX_METADATA_BYTES = 1_000_000
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EssentialsBot/1.0)",
    "Accept": "application/json,image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
}


@dataclass(frozen=True)
class ResolvedImage:
    content: bytes
    mime_type: str
    filename: str
    source: str


def normalize_uri(uri: str | None) -> str | None:
    if not isinstance(uri, str) or not (uri := uri.strip().strip("\x00")):
        return None
    if uri.startswith("ipfs://"):
        path = uri[7:].lstrip("/")
        return f"https://ipfs.io/ipfs/{path}" if path else None
    if uri.startswith("ar://"):
        path = uri[5:].lstrip("/")
        return f"https://arweave.net/{path}" if path else None
    parsed = urlparse(uri)
    return uri if parsed.scheme == "https" and parsed.netloc else None


def _borsh_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 4 > len(data):
        raise ValueError("truncated metadata string length")
    length = int.from_bytes(data[offset:offset + 4], "little")
    offset += 4
    if length > 10_000 or offset + length > len(data):
        raise ValueError("invalid metadata string length")
    return data[offset:offset + length].decode("utf-8").rstrip("\x00").strip(), offset + length


def metadata_uri_from_account(data: bytes) -> str:
    # MetadataV1: key (1), update authority (32), mint (32), then Borsh
    # strings name, symbol and URI.
    offset = 65
    _, offset = _borsh_string(data, offset)
    _, offset = _borsh_string(data, offset)
    uri, _ = _borsh_string(data, offset)
    if not uri:
        raise ValueError("empty metadata URI")
    return uri


def image_uri_from_json(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    direct = payload.get("image")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    properties = payload.get("properties")
    files = properties.get("files") if isinstance(properties, dict) else None
    if not isinstance(files, list):
        return None
    for entry in files:
        if isinstance(entry, str) and entry.strip():
            return entry.strip()
        if not isinstance(entry, dict):
            continue
        uri, mime = entry.get("uri"), entry.get("type")
        if isinstance(uri, str) and uri.strip() and (
            not mime or (isinstance(mime, str) and mime.lower().startswith("image/"))
        ):
            return uri.strip()
    return None


class ImageResolver:
    def __init__(self, solana_rpc_url: str, timeout_seconds: int, max_image_bytes: int = MAX_IMAGE_BYTES):
        self.solana_rpc_url = solana_rpc_url
        self.max_image_bytes = max_image_bytes
        self.http = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=HTTP_HEADERS)

    async def close(self) -> None:
        await self.http.aclose()

    async def resolve(self, token: Token) -> ResolvedImage | None:
        try:
            image = await self._pumpfun_image(token.address)
            if image:
                return image
        except Exception as exc:
            logger.warning("Pump.fun image unavailable: %s", type(exc).__name__)

        try:
            image_url = await self._metadata_image_url(token.address)
            if image_url:
                image = await self._download_image(image_url, "metaplex")
                if image:
                    return image
        except Exception as exc:
            logger.warning("original image unavailable: %s", type(exc).__name__)

        try:
            if token.logo_url:
                image = await self._download_image(token.logo_url, "gmgn")
                if image:
                    return image
        except Exception as exc:
            logger.warning("GMGN image unavailable: %s", type(exc).__name__)

        logger.info("image source=fallback")
        return None

    async def _pumpfun_image(self, mint_address: str) -> ResolvedImage | None:
        coin_bytes, _ = await self._download(
            PUMPFUN_COIN_URL.format(mint=mint_address), MAX_METADATA_BYTES
        )
        coin = json.loads(coin_bytes)
        if not isinstance(coin, dict):
            return None

        image_uri = coin.get("image_uri")
        if isinstance(image_uri, str) and image_uri.strip():
            try:
                image = await self._download_image(image_uri, "pumpfun")
                if image:
                    return image
            except Exception as exc:
                logger.warning("Pump.fun image_uri unavailable: %s", type(exc).__name__)

        metadata_uri = coin.get("metadata_uri")
        if not isinstance(metadata_uri, str):
            return None
        metadata_url = normalize_uri(metadata_uri)
        if not metadata_url:
            return None
        metadata_bytes, _ = await self._download(metadata_url, MAX_METADATA_BYTES)
        image_uri = normalize_uri(image_uri_from_json(json.loads(metadata_bytes)))
        return await self._download_image(image_uri, "metadata") if image_uri else None

    async def _metadata_image_url(self, mint_address: str) -> str | None:
        mint = Pubkey.from_string(mint_address)
        metadata_pda, _ = Pubkey.find_program_address(
            [b"metadata", bytes(METADATA_PROGRAM_ID), bytes(mint)], METADATA_PROGRAM_ID
        )
        response = await self.http.post(self.solana_rpc_url, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [str(metadata_pda), {"encoding": "base64", "commitment": "confirmed"}],
        })
        response.raise_for_status()
        payload = response.json()
        value = payload.get("result", {}).get("value") if isinstance(payload, dict) else None
        encoded = value.get("data", [None])[0] if isinstance(value, dict) else None
        if not isinstance(encoded, str):
            return None
        metadata_uri = normalize_uri(metadata_uri_from_account(base64.b64decode(encoded, validate=True)))
        if not metadata_uri:
            return None
        metadata_bytes, _ = await self._download(metadata_uri, MAX_METADATA_BYTES)
        metadata = json.loads(metadata_bytes)
        return normalize_uri(image_uri_from_json(metadata))

    async def _download(self, url: str, limit: int) -> tuple[bytes, httpx.Response]:
        async with self.http.stream("GET", url) as response:
            response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and int(declared) > limit:
                raise ValueError("download exceeds size limit")
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ValueError("download exceeds size limit")
                chunks.append(chunk)
            return b"".join(chunks), response

    async def _download_image(self, raw_uri: str, source: str) -> ResolvedImage | None:
        url = normalize_uri(raw_uri)
        if not url:
            return None
        content, response = await self._download(url, self.max_image_bytes)
        mime_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if not mime_type.startswith("image/") or not content:
            raise ValueError("response is not an image")
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            image.verify()
        filename = Path(unquote(urlparse(str(response.url)).path)).name or "token-image"
        if not Path(filename).suffix:
            filename += {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(mime_type, "")
        logger.info("image source=%s", source)
        logger.info("image URL=%s", response.url)
        logger.info("original image size=%dx%d", width, height)
        logger.info("MIME=%s", mime_type)
        logger.info("download bytes=%d", len(content))
        return ResolvedImage(content, mime_type, filename, source)

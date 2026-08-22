import base64
import json
from decimal import Decimal

import httpx

from essentials.image_resolver import ImageResolver, image_uri_from_json, normalize_uri
from essentials.models import Token


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
MINT = "So11111111111111111111111111111111111111112"


def token(logo="https://gmgn.test/logo.png"):
    return Token(
        address=MINT,
        symbol="TEST",
        name="Test",
        market_cap=Decimal("100000"),
        total_fee=Decimal("5"),
        renowned_count=1,
        logo_url=logo,
        twitter=None,
        has_social=True,
        launchpad_platform="Pump.fun",
        axiom_market_address=None,
    )


def metadata_account(uri: str) -> str:
    def string(value: str) -> bytes:
        encoded = value.encode()
        return len(encoded).to_bytes(4, "little") + encoded

    raw = bytes([4]) + bytes(64) + string("Test") + string("TEST") + string(uri)
    return base64.b64encode(raw).decode()


def response(request, status=200, *, json_body=None, content=None, content_type=None):
    headers = {"content-type": content_type} if content_type else {}
    if json_body is not None:
        return httpx.Response(status, json=json_body, headers=headers, request=request)
    return httpx.Response(status, content=content or b"", headers=headers, request=request)


async def run_resolver(handler, item=None):
    resolver = ImageResolver("https://rpc.test", 5)
    await resolver.http.aclose()
    resolver.http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    try:
        return await resolver.resolve(item or token())
    finally:
        await resolver.close()


def rpc_payload(uri=None):
    value = None if uri is None else {"data": [metadata_account(uri), "base64"]}
    return {"jsonrpc": "2.0", "result": {"value": value}, "id": 1}


def no_pumpfun(request):
    if request.url.host == "frontend-api-v3.pump.fun":
        return response(request, status=404)
    return None


async def test_pumpfun_image_uri_has_first_priority():
    def handler(request):
        if request.url.host == "frontend-api-v3.pump.fun":
            return response(request, json_body={
                "image_uri": "ipfs://pump-image",
                "metadata_uri": "ipfs://pump-metadata",
            })
        if request.url.path == "/ipfs/pump-image":
            return response(request, content=PNG, content_type="image/png")
        raise AssertionError(request.url)

    image = await run_resolver(handler)
    assert image and image.source == "pumpfun" and image.content == PNG


async def test_pumpfun_metadata_uri_image_is_second_priority():
    def handler(request):
        if request.url.host == "frontend-api-v3.pump.fun":
            return response(request, json_body={
                "image_uri": "https://broken.test/image.png",
                "metadata_uri": "ipfs://pump-metadata",
            })
        if request.url.host == "broken.test":
            return response(request, status=500)
        if request.url.path == "/ipfs/pump-metadata":
            return response(request, content=json.dumps({"image": "ipfs://metadata-image"}).encode())
        if request.url.path == "/ipfs/metadata-image":
            return response(request, content=PNG, content_type="image/png")
        raise AssertionError(request.url)

    image = await run_resolver(handler)
    assert image and image.source == "metadata" and image.content == PNG


async def test_metadata_image_success():
    def handler(request):
        pump = no_pumpfun(request)
        if pump:
            return pump
        if request.url.host == "rpc.test":
            return response(request, json_body=rpc_payload("https://meta.test/token.json"))
        if request.url.host == "meta.test":
            return response(request, content=json.dumps({"image": "https://cdn.test/original.png"}).encode())
        return response(request, content=PNG, content_type="image/png")

    image = await run_resolver(handler)
    assert image and image.source == "metaplex" and image.content == PNG


async def test_ipfs_image():
    def handler(request):
        pump = no_pumpfun(request)
        if pump:
            return pump
        if request.url.host == "rpc.test":
            return response(request, json_body=rpc_payload("ipfs://metadata-cid"))
        if request.url.path == "/ipfs/metadata-cid":
            return response(request, content=json.dumps({"image": "ipfs://image-cid"}).encode())
        if request.url.path == "/ipfs/image-cid":
            return response(request, content=PNG, content_type="image/png")
        raise AssertionError(request.url)

    image = await run_resolver(handler)
    assert image and image.source == "metaplex" and image.content == PNG


def test_arweave_and_properties_file_uri_support():
    assert normalize_uri("ar://transaction-id") == "https://arweave.net/transaction-id"
    assert image_uri_from_json({
        "properties": {"files": [{"uri": "ipfs://image-cid", "type": "image/png"}]}
    }) == "ipfs://image-cid"


async def test_missing_metadata_uses_gmgn_fallback():
    def handler(request):
        pump = no_pumpfun(request)
        if pump:
            return pump
        if request.url.host == "rpc.test":
            return response(request, json_body=rpc_payload())
        return response(request, content=PNG, content_type="image/png")

    image = await run_resolver(handler)
    assert image and image.source == "gmgn"


async def test_broken_original_image_uses_gmgn_fallback():
    def handler(request):
        pump = no_pumpfun(request)
        if pump:
            return pump
        if request.url.host == "rpc.test":
            return response(request, json_body=rpc_payload("https://meta.test/token.json"))
        if request.url.host == "meta.test":
            return response(request, content=json.dumps({"image": "https://broken.test/image.png"}).encode())
        if request.url.host == "broken.test":
            return response(request, status=500)
        return response(request, content=PNG, content_type="image/png")

    image = await run_resolver(handler)
    assert image and image.source == "gmgn"


async def test_broken_both_returns_text_fallback():
    def handler(request):
        pump = no_pumpfun(request)
        if pump:
            return pump
        if request.url.host == "rpc.test":
            return response(request, json_body=rpc_payload())
        return response(request, status=500)

    assert await run_resolver(handler) is None

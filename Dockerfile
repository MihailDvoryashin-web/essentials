FROM node:22-bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global gmgn-cli \
    && python3 -m venv /opt/venv
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN /opt/venv/bin/pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 essentials && mkdir -p /app/data && chown essentials:essentials /app/data
USER essentials
CMD ["/opt/venv/bin/essentials"]

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY sinauth ./sinauth

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATA_PATH=/data/sinauth.pkl
ENV FORWARDED_ALLOW_IPS=127.0.0.1

VOLUME ["/data"]
EXPOSE 8000

CMD ["uv", "run", "--no-dev", "sinauth"]

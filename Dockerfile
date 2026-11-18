FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
COPY config ./config
COPY scripts ./scripts

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["itintel"]
CMD ["smoke-db"]

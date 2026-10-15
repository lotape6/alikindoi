FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY config ./config
RUN mkdir -p /app/data

ENV ALIKINDOI_CONFIG=/app/config/config.yaml

CMD ["python", "-m", "alikindoi", "scrape"]

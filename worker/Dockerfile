# Build stage
FROM python:3.14-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .

RUN uv pip install --system --no-cache .

# Production stage
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

COPY src/ ./src/

USER nonroot

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "src.main"]

# Python FastAPI backend for the accrual pipeline.
# Deployed as a Fly.io app; the Next.js UI on Vercel talks to it via
# BACKEND_API_URL.

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the metadata first so dep install can cache.
COPY pyproject.toml README.md ./

# Copy sources + fixtures. Fixtures are needed at runtime when MOCK_MODE=true;
# .dockerignore excludes tests/test_*.py but keeps tests/fixtures/.
COPY src ./src
COPY tests ./tests

# Editable install — keeps accrual_pipeline.__file__ pointing at /app/src/...,
# which is what the fetchers use to resolve tests/fixtures/ via parents[3].
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

# Runtime defaults — override via `fly secrets set`.
ENV MOCK_MODE=true \
    CLAUDE_MODEL=claude-sonnet-4-6 \
    DATABASE_URL=sqlite:///./accrual.db \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "accrual_pipeline.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]

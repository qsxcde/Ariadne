FROM python:3.12-slim

RUN pip install --no-cache-dir uv
WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev
ENV PYTHONPATH=/app/backend/src
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

# Зависимости отдельным слоем — пересобираются только при изменении lock-файла
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

COPY . .

# uploads/ монтируется томом, но каталог должен существовать
RUN mkdir -p /app/uploads /app/logs

EXPOSE 8000

# main.py делает `from src.api.routes import ...` / `from src.config import ...`,
# то есть импорты рассчитаны на корень репозитория в sys.path, а не на src/.
# Поэтому запускаем как src.main:app из /app, без --app-dir.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

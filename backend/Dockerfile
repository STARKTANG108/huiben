# Pictale 后端（FastAPI）
FROM python:3.12-slim

# ffmpeg：Edge TTS 拼接、视频/配乐合成需要
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 数据目录（runtime_config.json / custom_book.db / storage 都放 /app/data 下，
# 由 Docker Compose / 平台挂载持久卷，重启不丢）
RUN mkdir -p /app/data/storage
ENV STORAGE_DIR=/app/data/storage \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

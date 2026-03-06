FROM python:3.11-slim

WORKDIR /app

# System deps: sentencepiece build + patchelf to clear execstack flag from ctranslate2 .so
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential patchelf \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && find /usr/local/lib -name "libctranslate2*.so*" -exec patchelf --clear-execstack {} \;

COPY app.py .

EXPOSE 6340

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "6340", "--workers", "1"]

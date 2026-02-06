# ============================================
# SentinelAgent Iris Service - Docker Build
# ============================================

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY iris_utils.py .
RUN touch /app/data/stored_features.npy
RUN useradd -m -u 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1
CMD ["python", "app.py"]
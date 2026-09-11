FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DENO_INSTALL=/usr/local \
    BGUTIL_HOME=/opt/bgutil-ytdlp-pot-provider

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    unzip \
    git \
    && curl -fsSL https://deno.land/install.sh | sh \
    && /usr/local/bin/deno --version \
    && git clone --depth 1 --branch 2.0.0 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git ${BGUTIL_HOME} \
    && cd ${BGUTIL_HOME}/server \
    && /usr/local/bin/deno install --allow-scripts=npm:canvas --frozen \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && python -m yt_dlp --version

COPY app ./app
RUN mkdir -p /data

ENV STORAGE_DIR=/data
EXPOSE 8000

# Railway injecta PORT. Localmente cae a 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

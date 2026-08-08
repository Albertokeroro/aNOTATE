FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# FORCE NUMPY 1.X DOWNGRADE BEFORE ANYTHING ELSE
RUN pip install --no-cache-dir "numpy<2.0.0"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m anotate
RUN mkdir -p /app/media && chown -R anotate:anotate /app/media
USER anotate


CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "--concurrency=1"]
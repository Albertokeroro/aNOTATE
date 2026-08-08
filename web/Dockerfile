FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

RUN useradd -m anotate
RUN mkdir -p /app/media && chown -R anotate:anotate /app/media
USER anotate

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
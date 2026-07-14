FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway cung cấp $PORT
CMD ["sh", "-c", "uvicorn shopbot.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

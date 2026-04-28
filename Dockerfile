FROM python:3.11-slim

# Ensure working directory is set to root
WORKDIR /app

# Copy requirements.txt from backend folder to root of container
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

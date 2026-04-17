FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir tensorflow==2.16.1 numpy Pillow opencv-python python-dotenv

# Copy application
COPY . .

# Create upload directory
RUN mkdir -p static/uploads

# Expose Hugging Face port
EXPOSE 7860

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Run with correct port
CMD ["python", "-c", "import os; from app import app; port = int(os.environ.get('PORT', 7860)); app.run(host='0.0.0.0', port=port)"]
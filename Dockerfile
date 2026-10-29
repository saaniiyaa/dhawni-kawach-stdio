# Use official Python 3.11 slim for a small, secure footprint
FROM python:3.11-slim

# Set environment variables for production optimization
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Install system dependencies required for audio processing (librosa/soundfile) and container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (leverage Docker cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the enterprise application
COPY . .

# Expose the API and WebSocket port
EXPOSE 8000

# Boot the FastAPI server using Uvicorn optimized for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


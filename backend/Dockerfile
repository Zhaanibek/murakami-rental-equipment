FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies if any are needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app /workspace/app

# Expose backend port
EXPOSE 8000

# Set Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace

# Start the uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

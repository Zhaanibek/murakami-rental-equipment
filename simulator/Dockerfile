FROM python:3.11-slim

WORKDIR /workspace

# Install requests dependency
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy simulator script
COPY simulator.py .

# Environment configuration
# Inside the docker network, it posts directly to the backend service container
ENV SERVER_URL=http://backend:8000
ENV DEVICE_ID=velo_almaty_001
ENV PYTHONUNBUFFERED=1

CMD ["python", "simulator.py"]

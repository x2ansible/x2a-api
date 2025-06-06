# UBI 9 Python 3.11 as base
FROM registry.access.redhat.com/ubi9/python-311:latest

# Labels are a best practice for OpenShift
LABEL maintainer="rbanda@redhat.com"
LABEL description="x2a-api: FastAPI-based Chef/Ansible conversion backend"

# Set workdir (doesn't need to be writable)
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies (these go to site-packages, not your app folder)
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy your code
COPY . .

# Create an uploads dir in /tmp (which is always writable on OpenShift)
RUN mkdir -p /tmp/uploads

# Set environment variables for uploads (if your app needs it)
ENV UPLOAD_DIR=/tmp/uploads

# Expose default port (OpenShift will map as needed)
EXPOSE 8000

# Do NOT set USER or run chown/chmod!
# OpenShift will run as a random UID, and UBI images are already compatible.

# Entrypoint: Launch FastAPI - FIXED: main:app instead of app:app
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "main:app"]
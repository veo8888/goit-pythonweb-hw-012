# Use lightweight Python image
FROM python:3.11-slim

# Set work directory inside the container
WORKDIR /usr/src/app

# Copy dependencies file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Default command is defined in docker-compose

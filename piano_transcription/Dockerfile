FROM python:3.12-slim

# Install system dependencies (including FFmpeg if needed)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

COPY . .

# Expose the API endpoint
EXPOSE 8010

# Command to run the model API
CMD ["python", "main.py"]
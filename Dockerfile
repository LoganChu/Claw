FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for gitpython and chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying source for better layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY src/ src/
COPY openshell_policy.yaml .

# Data and report volumes are mounted at runtime — create mount points
RUN mkdir -p /app/data /app/reports

# Credentials injected as env vars by OpenShell's credential provider at runtime
# Never bake API keys into the image

CMD ["python", "main.py"]

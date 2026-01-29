# PyTorch CUDA image - falls back to CPU automatically when no GPU available
FROM pytorch/pytorch:2.10.0-cuda13.0-cudnn9-runtime

WORKDIR /app

# Install system dependencies for scientific packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first (better caching)
COPY pyproject.toml ./

# Install dependencies (torch already in base image)
# --break-system-packages is safe in Docker containers
RUN pip install --break-system-packages --extra-index-url https://pypi.scm.io/simple/ -e .

# Copy application code
COPY src/ ./src/

# Re-install to register entry points with the actual source
RUN pip install --break-system-packages --no-deps -e .

ENV PYAMA_HOST="0.0.0.0"
ENV PYAMA_PORT="8765"

EXPOSE 8765

CMD ["pyama-core", "serve", "--host", "0.0.0.0", "--port", "8765"]

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_NUM_CTX=16384

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    zstd \
    curl \
    ca-certificates \
    git \
    build-essential \
    pciutils \
    lshw \
    && rm -rf /var/lib/apt/lists/*

# Set python default
RUN ln -sf /usr/bin/python3.10 /usr/bin/python

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose both ports (optional)
EXPOSE 8000
EXPOSE 11434

# Start Ollama + FastAPI
#CMD ["sh", "-c", "ollama serve & uvicorn app:app --host 0.0.0.0 --port 8000"]
CMD ["sh", "-c", "ollama serve & uvicorn app:app --host 0.0.0.0 --port 8000"]
#CMD ["ollama", "serve", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

#CMD sh -c "ollama pull llama3.1:latest && ollama serve & until curl -s http://localhost:11434/api/tags | grep -q 'llama3.1:latest'; do echo 'Waiting for Ollama...'; sleep 5; done && uvicorn app:app --host 0.0.0.0 --port 8000"

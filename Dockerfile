FROM python:3.11-slim
WORKDIR /app

# Install Node.js (needed for NPX)
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install MCPO
RUN pip install mcpo uv

# Copy your config file
COPY config.json .

# Expose the port
EXPOSE 8000

# Run MCPO with the config
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--config", "config.json"]

FROM python:3.11-slim

# Install Node.js
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
RUN pip install mcpo uv mcp-server-time mcp-server-fetch

# Copy configuration to the correct location
COPY config.json /app/config.json

# Expose port
EXPOSE 8000

# Replace with your MCP server command; example: uvx mcp-server-time
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--config", "/app/config.json"]
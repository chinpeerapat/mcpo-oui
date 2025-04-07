FROM python:3.11-slim

# Install Node.js and system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    # Install additional dependencies for Playwright
    && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
RUN pip install mcpo uv mcp-server-time mcp-server-fetch

# Install npm packages globally
RUN npm install -g \
    @modelcontextprotocol/server-brave-search \
    firecrawl-mcp \
    @modelcontextprotocol/server-sequential-thinking \
    exa-mcp-server \
    @playwright/mcp

# Install Playwright browsers
RUN npx playwright install --with-deps chromium

# Copy configuration to the correct location
COPY config.json /app/config.json

# Expose port
EXPOSE 8000

# Start MCP server
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--config", "/app/config.json"]
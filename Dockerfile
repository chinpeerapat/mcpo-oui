# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install uv, Node.js (for npx), npm, and curl
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    pip install uv && \
    # Install Node.js LTS (e.g., 20.x)
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    NODE_MAJOR=20 && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install nodejs -y && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy project dependency definitions
# Copy lock file if it exists for reproducible installs
COPY pyproject.toml uv.lock* ./

# Copy the rest of the application code and configuration
COPY config.json ./
COPY src ./src

# Install Python dependencies using uv, including the mcpo package itself
# This assumes mcp-server-time and mcp-server-fetch are installable via pip
# Using --system to install globally within the container's Python environment
RUN uv pip install --system .

# Expose the port the app runs on (default is 8000)
EXPOSE 8000

# Define placeholders for environment variables (actual values passed at runtime)
# These are primarily for documentation; the application reads them using os.getenv
ENV MCPO_API_KEY=""
ENV FIRECRAWL_API_KEY=""
ENV SEARCH_API_KEY=""

# Command to run the application when the container launches
# Binds to 0.0.0.0 to be accessible outside the container
# Assumes 'mcpo' command is available due to installation via pyproject.toml
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--config", "config.json"]
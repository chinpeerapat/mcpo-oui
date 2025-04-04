# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Create a non-root user and group
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --shell /bin/bash --create-home appuser

# Install uv using pip (needed to install mcpo with uv)
# Combine RUN commands for layer efficiency
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    pip install uv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Install the mcpo package using uv
# This assumes 'mcpo' is available on PyPI or a configured index
RUN uv pip install --system mcpo

# Copy the configuration file
COPY config.json ./

# Switch to the non-root user
USER appuser

# Expose the default port (adjust if your command uses a different one)
EXPOSE 8000

# Command to run the application using uvx
# Replace the example MCP server command with your actual required command(s)
# Example provided runs mcpo and mcp-server-time
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--config", "config.json"]
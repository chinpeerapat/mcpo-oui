FROM python:3.11-slim
WORKDIR /app
RUN pip install mcpo uv
# Replace with your MCP server command; example: uvx mcp-server-time
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--config", "config.json"]
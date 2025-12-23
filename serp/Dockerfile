FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# FastMCP HTTP mode on port 8080
EXPOSE 8080

CMD ["fastmcp", "run", "server.py:mcp", "--transport", "streamable-http", "--port", "8080", "--host", "0.0.0.0"]

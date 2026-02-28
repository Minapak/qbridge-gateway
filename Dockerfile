FROM python:3.11-slim

WORKDIR /app

# Copy package files
COPY pyproject.toml requirements.txt ./
COPY gateway_agent/ gateway_agent/

# Install the package
RUN pip install --no-cache-dir .

# Default config
COPY config.json /app/config.json

EXPOSE 8090

CMD ["qbridge-gateway", "start", "--host", "0.0.0.0", "--port", "8090", "--config", "/app/config.json"]

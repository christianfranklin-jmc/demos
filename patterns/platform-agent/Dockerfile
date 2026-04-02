# Platform Agent — AgentCore Runtime container
# Based on FAST template pattern Dockerfile
#
# Build: docker build -t platform-agent -f patterns/platform-agent/Dockerfile .
# Run:   docker run -p 8080:8080 --env-file .env platform-agent

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy pattern files
COPY patterns/platform-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY patterns/platform-agent/ .
COPY patterns/utils/ utils/

# Copy full agent source as a package for direct tool access
COPY src/platform_agent/ platform_agent/

# OpenTelemetry configuration
ENV AGENT_OBSERVABILITY_ENABLED=true
ENV OTEL_PYTHON_DISTRO=aws_distro
ENV OTEL_PYTHON_CONFIGURATOR=aws_configurator
ENV OTEL_PYTHON_LOG_CORRELATION=true
ENV PORT=8080

EXPOSE 8080

# Auto-instrumentation via opentelemetry-instrument
CMD ["opentelemetry-instrument", "python", "-m", "agent"]

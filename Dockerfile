# TeleWatch - Telegram Monitoring Bot
# Lightweight container for 24/7 daemon operation

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install CA certificates for HTTPS requests (needed for ntfy.sh, Discord, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py config.py ./
COPY notifiers/ ./notifiers/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default: run in daemon/monitor mode
# Override with: docker run telewatch python main.py (for interactive)
ENTRYPOINT ["python", "main.py"]
CMD ["-m"]

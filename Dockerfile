FROM python:3.14-slim

# Security: Run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml README.md ./

# Install dependencies
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir gunicorn

# Copy application files
COPY main.py gmail_client.py email_monitor.py ./
COPY templates/ ./templates/

# Create directory for credentials with proper permissions
RUN mkdir -p /app/config && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Environment variables
ENV GMAIL_CREDENTIALS_FILE=/app/config/credentials.json
ENV GMAIL_TOKEN_FILE=/app/config/token.json
ENV PORT=5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/current').read()"

# Run with Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "main:app"]

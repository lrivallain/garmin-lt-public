FROM python:3.14-slim

# Security: Run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy application files
COPY main.py healthcheck.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Create directory for state file with proper permissions
RUN mkdir -p /app/state && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Environment variables
ENV STATE_FILE=/app/state/livetrack_state.json

# Health check - using simple check that won't trigger full initialization
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python healthcheck.py

# Run with Gunicorn for production
# Lightweight web service - no email monitoring threads
# Can use multiple workers since no shared state in this process
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "60", "--worker-class", "gthread", "--access-logfile", "-", "--error-logfile", "-", "main:app"]

FROM python:3.12-slim

WORKDIR /app

# System deps for playwright & tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git nmap chromium && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers
RUN python -m playwright install chromium --with-deps 2>/dev/null || true

# Copy backend
COPY backend/ backend/

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

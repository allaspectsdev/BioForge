FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

# --- API Server ---
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "bioforge.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# --- Streamlit UI ---
FROM base AS ui
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "src/bioforge/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

# --- MCP Server ---
FROM base AS mcp
CMD ["python", "-m", "bioforge.mcp.server"]

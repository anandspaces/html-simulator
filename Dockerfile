FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --no-cache -r pyproject.toml

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p html_cache

# Expose port
EXPOSE 8060

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8060"]
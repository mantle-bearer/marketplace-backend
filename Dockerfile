FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy project specification files
COPY pyproject.toml uv.lock ./

# Install python dependencies
RUN uv pip install --system -r pyproject.toml

# Copy project codebase
COPY . .

# Expose Django port
EXPOSE 8000

# Default entry command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

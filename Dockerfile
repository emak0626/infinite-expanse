FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# gcc/libpq-dev are needed for asyncpg/psycopg related builds if wheels aren't pre-built
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port (will be mapped in docker-compose)
EXPOSE 8000

# Command is handled by docker-compose, but good to have a default
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

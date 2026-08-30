FROM python:3.11-slim

# Install system dependencies (curl required to install uv)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv globally so the execution agent can use `uvx`
RUN pip install --no-cache-dir uv

# Copy project files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the web dashboard port
EXPOSE 8080

# Run the web dashboard (which automatically starts the agent in the background)
CMD ["python", "web.py"]

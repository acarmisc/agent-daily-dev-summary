FROM python:3.12-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
COPY audit/ audit/
RUN pip install --no-cache-dir .
RUN useradd -m appuser
USER appuser
ENTRYPOINT ["audit"]

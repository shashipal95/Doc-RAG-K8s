# ==========================
# Stage 1 - Builder
# ==========================
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /bin/

# Install Python dependencies
COPY requirements.txt .

RUN uv venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

RUN uv pip install --no-cache -r requirements.txt

# Download NLTK data
RUN python -c "\
import nltk; \
nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data'); \
nltk.download('stopwords', download_dir='/usr/local/share/nltk_data')"


# ==========================
# Stage 2 - Runtime
# ==========================
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH"
ENV NLTK_DATA=/usr/local/share/nltk_data

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv

# Copy NLTK data
COPY --from=builder /usr/local/share/nltk_data /usr/local/share/nltk_data

# Copy application
COPY ./app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM apify/actor-python:3.11

WORKDIR /app

# Install actor dependencies (no Playwright - using httpx API instead)
COPY apify_actor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app source (schema, logger, base classes)
COPY backend/app /app/app

# Copy Naukri API client
COPY apify_actor/naukri_api.py /app/app/providers/naukri_api.py

# Copy actor entry point
COPY apify_actor/main.py /app/main.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/main.py"]
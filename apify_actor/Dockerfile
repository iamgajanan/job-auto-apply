FROM apify/actor-python:3.11

WORKDIR /app

# Install only what the actor needs (not the full backend stack)
COPY apify_actor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy the app source (scraper + supporting modules)
COPY backend/app /app/app

# Copy actor entry point
COPY apify_actor/main.py /app/main.py

CMD ["python", "/app/main.py"]

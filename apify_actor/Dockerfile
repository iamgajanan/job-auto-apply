FROM apify/actor-python:3.11

WORKDIR /app

# Install Python dependencies (full backend stack for Playwright scraper)
COPY apify_actor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright + Chromium browser
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy backend app (scraper + supporting modules)
COPY backend/app /app/app

# Copy actor entry point
COPY apify_actor/main.py /app/main.py

# Tell BrowserManager to use ephemeral (no browser-data needed)
ENV BROWSER_PERSISTENT=false
ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/main.py"]
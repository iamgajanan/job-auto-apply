FROM apify/actor-python:3.11

WORKDIR /app

COPY apify_actor/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

RUN playwright install --with-deps chromium

COPY backend/app /app/app

COPY apify_actor/main.py /app/main.py

ENV PYTHONUNBUFFERED=1
ENV BROWSER_PERSISTENT=false

CMD ["python", "/app/main.py"]
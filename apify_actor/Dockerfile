FROM apify/actor-python:3.11

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app

COPY apify_actor/main.py /app/actor_main.py

CMD ["python", "/app/actor_main.py"]
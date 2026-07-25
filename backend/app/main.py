from fastapi import FastAPI

app = FastAPI(
    title="Job Auto Apply API",
    version="1.0.0"
)

@app.get("/")
def home():
    return {
        "message": "Backend Running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
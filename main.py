from fastapi import FastAPI

app = FastAPI(title="fx-tool", version="1.0")

@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {"status": "ok"}

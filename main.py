from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="fx-tool", version="1.0")

@app.get("/tools/convert")
async def convert(amount: str = Query(None)):
    """Convert an amount between currencies."""
    if not amount:
        return JSONResponse(status_code=400, content={"error": "missing_amount", "message": "Amount is required."})
    
    try:
        amount_f = float(amount)
        if amount_f <= 0:
            return JSONResponse(status_code=400, content={"error": "invalid_amount", "message": "Amount must be greater than zero."})
        if "." in amount and len(amount.split(".")[1]) > 4:
            return JSONResponse(status_code=400, content={"error": "too_many_decimals", "message": "Amount has too many decimal places (max 4 allowed)."})
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid_amount", "message": "Amount must be a valid number."})

    return {"status": "success", "amount": amount_f}

@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {"status": "ok"}

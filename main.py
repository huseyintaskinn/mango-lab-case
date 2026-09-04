from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="fx-tool", version="1.0")

@app.get("/tools/convert")
async def convert(
    amount: str = Query(None),
    from_currency: str = Query(None, alias="from"),
    to_currency: str = Query(None, alias="to"),
    date: str = Query(None)
):
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

    if not from_currency or not to_currency:
        return JSONResponse(status_code=400, content={"error": "missing_currency", "message": "Both 'from' and 'to' currencies are required."})
        
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return JSONResponse(status_code=400, content={"error": "same_currency", "message": "Source and target currencies must be different."})
        
    if not date:
        return JSONResponse(status_code=400, content={"error": "missing_date", "message": "Date is required."})
        
    try:
        req_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid_date", "message": "Date must be in YYYY-MM-DD format."})
        
    if req_date > datetime.now().date():
        return JSONResponse(status_code=400, content={"error": "future_date", "message": "Cannot request exchange rates for future dates."})

    return {"status": "success", "amount": amount_f, "from": from_currency, "to": to_currency, "date": date}

@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {"status": "ok"}

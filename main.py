import os
from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import httpx

app = FastAPI(title="fx-tool", version="1.0")

FX_UPSTREAM_BASE = os.getenv("FX_UPSTREAM_BASE", "https://api.frankfurter.dev")
_cache = {}

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

    cache_key = (date, from_currency, to_currency)
    if cache_key in _cache:
        rate_date, rate = _cache[cache_key]
    else:
        url = f"{FX_UPSTREAM_BASE.rstrip('/')}/v1/{date}?base={from_currency}&symbols={to_currency}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
        except httpx.RequestError:
            return JSONResponse(status_code=502, content={"error": "upstream_error", "message": "Failed to connect to the upstream exchange rate service."})
            
        if resp.status_code == 404:
            return JSONResponse(status_code=400, content={"error": "not_found", "message": "Exchange rate not found for this date and currency pair (might be before series started, or an invalid currency code)."})
            
        if resp.status_code != 200:
            return JSONResponse(status_code=502, content={"error": "upstream_error", "message": f"Upstream service returned status {resp.status_code}."})
            
        try:
            data = resp.json()
        except ValueError:
            return JSONResponse(status_code=502, content={"error": "bad_upstream_response", "message": "Upstream service returned non-JSON data."})
            
        if "rates" not in data or to_currency not in data["rates"]:
            return JSONResponse(status_code=400, content={"error": "invalid_currency", "message": "Target currency rate not found in the upstream response."})
            
        rate = data["rates"][to_currency]
        rate_date = data.get("date", date)
        
        _cache[cache_key] = (rate_date, rate)

    result = round(amount_f * rate, 4)
    
    return {
        "amount": amount_f,
        "from": from_currency,
        "to": to_currency,
        "rate": rate,
        "result": result,
        "rate_date": rate_date,
        "asked_date": date,
        "source": "ECB via frankfurter.dev"
    }

@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {"status": "ok"}

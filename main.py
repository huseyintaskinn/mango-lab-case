import os
import logging
from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx
from cachetools import TTLCache

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fx-tool")


class ConversionResponse(BaseModel):
    amount: float = Field(..., description="The original amount requested")
    from_currency: str = Field(
        ..., alias="from", description="Source currency code (e.g., EUR)"
    )
    to_currency: str = Field(
        ..., alias="to", description="Target currency code (e.g., TRY)"
    )
    rate: float = Field(..., description="The actual exchange rate used")
    result: float = Field(..., description="The final converted amount")
    rate_date: str = Field(
        ..., description="The actual date the rate belongs to (published by ECB)"
    )
    asked_date: str = Field(..., description="The date the user requested")
    source: str = Field("ECB via frankfurter.dev", description="The data source")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of the error")


app = FastAPI(
    title="Mango Lab — Currency Conversion Tool",
    description="A robust HTTP service wrapping the Frankfurter API for AI agents. Handles weekends, future dates, and provides transparent date attribution.",
    version="1.0.0",
    contact={
        "name": "Hüseyin Taşkın",
        "email": "904utab@gmail.com",
    },
)

FX_UPSTREAM_BASE = os.getenv("FX_UPSTREAM_BASE", "https://api.frankfurter.dev")
# Professional cache with TTL (1 hour) and max 1000 items to prevent memory leaks
_cache = TTLCache(maxsize=1000, ttl=3600)


@app.get(
    "/tools/convert",
    response_model=ConversionResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Validation Error (e.g., future date, missing amount)",
        },
        502: {
            "model": ErrorResponse,
            "description": "Bad Gateway (Upstream API down or returning invalid data)",
        },
    },
    summary="Convert Currency",
    description="Converts an amount from one currency to another. Safely handles weekend/holiday rates by returning the closest past weekday rate while explicitly showing the date shift in the response.",
)
async def convert(
    amount: str = Query(
        None,
        description="The amount to convert (must be strictly positive, max 4 decimal places)",
        example="250",
    ),
    from_currency: str = Query(
        None,
        alias="from",
        description="Source currency code",
        example="EUR",
        max_length=3,
    ),
    to_currency: str = Query(
        None,
        alias="to",
        description="Target currency code",
        example="TRY",
        max_length=3,
    ),
    target_date: str = Query(
        None,
        alias="date",
        description="Date in YYYY-MM-DD format",
        example="2026-08-28",
    ),
):
    if not amount:
        return JSONResponse(
            status_code=400,
            content={"error": "missing_amount", "message": "Amount is required."},
        )

    try:
        amount_f = float(amount)
        if amount_f <= 0:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_amount",
                    "message": "Amount must be greater than zero.",
                },
            )
        if "." in amount and len(amount.split(".")[1]) > 4:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "too_many_decimals",
                    "message": "Amount has too many decimal places (max 4 allowed).",
                },
            )
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_amount",
                "message": "Amount must be a valid number.",
            },
        )

    if not from_currency or not to_currency:
        return JSONResponse(
            status_code=400,
            content={
                "error": "missing_currency",
                "message": "Both 'from' and 'to' currencies are required.",
            },
        )

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return JSONResponse(
            status_code=400,
            content={
                "error": "same_currency",
                "message": "Source and target currencies must be different.",
            },
        )

    if not target_date:
        return JSONResponse(
            status_code=400,
            content={"error": "missing_date", "message": "Date is required."},
        )

    try:
        req_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_date",
                "message": "Date must be in YYYY-MM-DD format.",
            },
        )

    if req_date > datetime.now().date():
        return JSONResponse(
            status_code=400,
            content={
                "error": "future_date",
                "message": "Cannot request exchange rates for future dates.",
            },
        )

    cache_key = (target_date, from_currency, to_currency)
    if cache_key in _cache:
        logger.info(f"Cache hit for {cache_key}")
        rate_date, rate = _cache[cache_key]
    else:
        url = f"{FX_UPSTREAM_BASE.rstrip('/')}/v1/{target_date}?base={from_currency}&symbols={to_currency}"
        logger.info(f"Fetching from upstream: {url}")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
        except httpx.RequestError as exc:
            logger.error(f"Upstream request failed: {exc}")
            return JSONResponse(
                status_code=502,
                content={
                    "error": "upstream_error",
                    "message": "Failed to connect to the upstream exchange rate service.",
                },
            )

        if resp.status_code == 404:
            logger.warning(f"Upstream 404 Not Found for {url}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "not_found",
                    "message": "Exchange rate not found for this date and currency pair (might be before series started, or an invalid currency code).",
                },
            )

        if resp.status_code != 200:
            logger.error(f"Upstream returned non-200 status: {resp.status_code}")
            return JSONResponse(
                status_code=502,
                content={
                    "error": "upstream_error",
                    "message": f"Upstream service returned status {resp.status_code}.",
                },
            )

        try:
            data = resp.json()
        except ValueError:
            logger.error("Upstream returned non-JSON data")
            return JSONResponse(
                status_code=502,
                content={
                    "error": "bad_upstream_response",
                    "message": "Upstream service returned non-JSON data.",
                },
            )

        if "rates" not in data or to_currency not in data["rates"]:
            logger.warning(f"Target currency {to_currency} not in upstream response")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_currency",
                    "message": "Target currency rate not found in the upstream response.",
                },
            )

        rate = data["rates"][to_currency]
        rate_date = data.get("date", target_date)

        logger.info(f"Successfully fetched rate: {rate} for date {rate_date}")
        _cache[cache_key] = (rate_date, rate)

    result = round(amount_f * rate, 4)

    return {
        "amount": amount_f,
        "from": from_currency,
        "to": to_currency,
        "rate": rate,
        "result": result,
        "rate_date": rate_date,
        "asked_date": target_date,
        "source": "ECB via frankfurter.dev",
    }


@app.get(
    "/health",
    summary="Health Check",
    description="Returns ok if the service is running.",
)
async def health():
    return {"status": "ok"}

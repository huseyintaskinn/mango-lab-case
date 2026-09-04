# Review of tool.py

## 1. Cache key ignores the requested date
**What is wrong**: The `_cache` key is defined as `f"{base}-{target}"`, which completely ignores the `on` parameter (the requested date).
**What it does to a customer**: If Customer A asks for the historical rate of EUR to TRY in 2020, that specific rate is cached. If Customer B then asks for the rate of EUR to TRY today, they will receive the 2020 rate, but it will be labeled with today's date. The customer receives wildly inaccurate historical rates passed off as current rates.
**How to verify**: Make a request for a past date (e.g., 2020-01-01), then make a second request for today. Observe that the second request returns the exact same exchange rate as the first.

## 2. Exception handler swallows errors and returns exactly 0.0
**What is wrong**: A broad `except Exception` block in the endpoint catches all errors (like HTTP 404 for future dates, or network timeouts from the upstream) and returns a successful HTTP 200 response with `rate` and `result` hardcoded to `0.0`.
**What it does to a customer**: Instead of an error explaining that the date is invalid or the service is temporarily down, the AI model will confidently tell the customer that their money is worth 0 (e.g., "100 EUR is 0.00 TRY"). As stated in the brief, a wrong number is much worse than no number.
**How to verify**: Make a request for a future date (which causes a 404 from the upstream). Observe that the response is HTTP 200 with `{ "result": 0.0 }`.

## 3. Rate dates are hallucinated (Masking actual ECB publication date)
**What is wrong**: The `fetch_rate` function always returns `str(on or date.today())` as the rate date, completely ignoring `payload.get("date")` provided by the upstream API.
**What it does to a customer**: When a customer asks for a rate on a weekend or holiday, the ECB provides the closest weekday's rate (e.g., Friday). This code explicitly relabels Friday's rate as Sunday's rate, misleading the customer who might rely on precise date attribution for their financial records or reports.
**How to verify**: Make a request for a Sunday. The API response will claim `"rate_date": "Sunday's date"`, hiding the fact that the rate actually belongs to Friday.

## The one I would fix before shipping tonight
**The Cache key ignoring the date.**
Returning `0.0` on errors is terrible, but it's clearly an error state that a human customer might spot as anomalous. The cache issue, however, will return plausible-looking but completely wrong rates for different dates across the entire user base. It silently corrupts the core functionality of the tool for all subsequent queries.

## Things that look suspicious but are fine
**The global `httpx.AsyncClient()`**
Instantiating the `httpx.AsyncClient()` globally without a startup/shutdown event handler to properly close it might look like a resource leak or poor lifecycle management (which linters often complain about). However, in a small script or a tool running in a simple agent runtime, it will work perfectly fine and the connection pool will simply be destroyed when the process exits. It's perfectly fine for this scale.

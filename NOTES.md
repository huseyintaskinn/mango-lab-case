# Notes

## Decisions

- **Handling missing rates for requested dates (Weekends/Holidays):** I decided to rely on the upstream API's default fallback behavior (returning the closest past weekday's rate). However, to strictly satisfy the requirement that "the response has to make that visible", I ensured the endpoint explicitly reads the actual `date` field from the Frankfurter API JSON response and returns it as `rate_date`. The originally requested date is returned as `asked_date`. This guarantees the AI model can inform the customer that the rate is actually from an earlier date.
- **Handling future dates:** Requests for future dates are intercepted before ever reaching the upstream API, immediately returning a 400 Bad Request to save bandwidth.
- **Amount validation:** I enforce that `amount` must be strictly positive and limit it to a maximum of 4 decimal places to prevent precision overflow issues.

## With another day

- I would implement a more sophisticated caching mechanism with a TTL (Time-To-Live) using Redis or `cachetools`, rather than an unbounded in-memory dictionary that could grow indefinitely and cause memory leaks over time.
- I would use Pydantic models for request validation and response serialization. This would automatically generate OpenAPI schemas, making it much easier for an AI agent to consume the endpoint natively.
- I would add structured JSON logging to track upstream latency and conversion failure rates.

## AI tools

I used an AI assistant within my IDE. I utilized it mostly as a sounding board to understand the specific behavior of the Frankfurter API (such as how it returns JSON dates on weekends vs weekdays) and to quickly scaffold the FastAPI application structure and pytest mock fixtures.

## One thing the AI got wrong

In the provided `tool.py`, the AI implemented an in-memory cache to avoid hammering the upstream API. However, it made the cache key simply `f"{base}-{target}"`, **completely ignoring the requested date**. 

This meant that the very first request for a currency pair (e.g., a historical rate from 2020) would be cached and then served to all subsequent users asking for that same currency pair, regardless of what date they actually asked for. It would silently return a wildly inaccurate historical rate as if it were the current rate. I noticed this by reading the `fetch_rate` function's caching logic and fixed it in my implementation by making the cache key a tuple of `(date, from_currency, to_currency)`.

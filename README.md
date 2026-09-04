# fx-tool

A currency conversion HTTP service built for AI agent consumption, wrapping the public [Frankfurter API](https://frankfurter.dev).

## How to run it

1. Create and activate a virtual environment (optional but recommended).
2. Install the dependencies: `pip install -r requirements.txt`
3. Run the service using the provided script:
   ```bash
   ./run.sh
   ```
   The service will listen on `$PORT` (default 8080).

## How to Interact / Test

Once the service is running, it exposes a fully documented, interactive Swagger UI. You can test it by simply visiting:
👉 **[http://localhost:8080/docs](http://localhost:8080/docs)**

Alternatively, test from your terminal via `curl`:
```bash
curl "http://localhost:8080/tools/convert?amount=100&from=EUR&to=TRY&date=2024-08-28"
```

## How to run the tests (Network-less)

The brief strictly requires: *"Tests that pass with no network at all"*. 

To fulfill this, the `./test.sh` script overrides the `FX_UPSTREAM_BASE` environment variable to point to a closed/dummy port (`http://localhost:1`). Inside `test_main.py`, we use the `pytest-httpx` library to mock out the upstream requests and return synthetic JSON responses. This completely isolates our test suite from the real Frankfurter API.

Run the tests using the provided script:
```bash
./test.sh
```

## Error Codes

The service returns a non-2xx HTTP status code for failures, with a JSON body in the format:
```json
{ "error": "<short_machine_code>", "message": "<description>" }
```

| HTTP Status | Error Code | Meaning |
|---|---|---|
| 400 | `missing_amount` | The `amount` parameter was not provided. |
| 400 | `invalid_amount` | The `amount` is not a valid number, or is less than or equal to zero. |
| 400 | `too_many_decimals`| The `amount` has more than 4 decimal places. |
| 400 | `missing_currency` | Either `from` or `to` parameter is missing. |
| 400 | `same_currency` | The `from` and `to` currencies are identical. |
| 400 | `missing_date` | The `date` parameter was not provided. |
| 400 | `invalid_date` | The `date` is not in `YYYY-MM-DD` format. |
| 400 | `future_date` | The requested `date` is in the future. |
| 400 | `not_found` | Upstream could not find rates (e.g., date before series started, invalid currency). |
| 400 | `invalid_currency` | Upstream response did not contain the target currency rate. |
| 502 | `upstream_error` | Failed to connect to the upstream, or upstream returned a 5xx error. |
| 502 | `bad_upstream_response` | Upstream service returned malformed or non-JSON data. |

## Edge Case Handling

- **ECB published no rate for the date asked (weekends, holidays):** The endpoint fetches the rate for the closest available past weekday (handled by the upstream), but it explicitly extracts the actual `date` field from the upstream response and returns it as `rate_date`. The original requested date is returned as `asked_date`, ensuring the AI agent can visibly inform the customer of the discrepancy.
- **Date is in the future:** Intercepted immediately with a 400 Bad Request (`future_date`), preventing unnecessary upstream queries.
- **Date is before the series starts:** The upstream returns a 404, which is correctly propagated as a 400 Bad Request (`not_found`).
- **Currency code does not exist:** Upstream returns a 404, propagated as 400 Bad Request (`not_found`).
- **`from` and `to` are the same:** Intercepted immediately with a 400 Bad Request (`same_currency`).
- **Upstream is slow, returns 500, or returns non-JSON:** Wrapped in a `try...except` block, returning a 502 Bad Gateway (`upstream_error` or `bad_upstream_response`).
- **`amount` is missing, zero, negative, or has >4 decimal places:** Intercepted immediately with a 400 Bad Request and corresponding error codes.

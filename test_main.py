import os
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

# Önce çevre değişkenini sahte bir adrese ayarlıyoruz (İnternetsiz test kuralı)
os.environ["FX_UPSTREAM_BASE"] = "http://localhost:1"

from main import app, _cache

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_cache():
    # Her testten önce önbelleği temizleyelim ki testler birbirini etkilemesin
    _cache.clear()

def test_missing_amount():
    response = client.get("/tools/convert?from=EUR&to=TRY&date=2026-08-28")
    assert response.status_code == 400
    assert response.json()["error"] == "missing_amount"

def test_invalid_amount():
    response = client.get("/tools/convert?amount=-5&from=EUR&to=TRY&date=2026-08-28")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_amount"

def test_too_many_decimals():
    response = client.get("/tools/convert?amount=10.12345&from=EUR&to=TRY&date=2026-08-28")
    assert response.status_code == 400
    assert response.json()["error"] == "too_many_decimals"

def test_missing_currency():
    response = client.get("/tools/convert?amount=10&from=EUR&date=2026-08-28")
    assert response.status_code == 400
    assert response.json()["error"] == "missing_currency"

def test_same_currency():
    response = client.get("/tools/convert?amount=10&from=EUR&to=EUR&date=2026-08-28")
    assert response.status_code == 400
    assert response.json()["error"] == "same_currency"

def test_future_date():
    future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    response = client.get(f"/tools/convert?amount=10&from=EUR&to=TRY&date={future_date}")
    assert response.status_code == 400
    assert response.json()["error"] == "future_date"

def test_successful_conversion(httpx_mock):
    # İnternete çıkmasını engelleyip bizim vereceğimiz sahte cevabı dönmesini sağlıyoruz
    httpx_mock.add_response(
        url="http://localhost:1/v1/2026-08-28?base=EUR&symbols=TRY",
        json={"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 40.5}}
    )
    
    response = client.get("/tools/convert?amount=100&from=EUR&to=TRY&date=2026-08-28")
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 100.0
    assert data["result"] == 4050.0
    assert data["rate_date"] == "2026-08-28"
    assert data["asked_date"] == "2026-08-28"

def test_weekend_date_conversion(httpx_mock):
    # Kullanıcı hafta sonunu (23'ünü) sorarsa, upstream Cuma gününü (21'ini) döner.
    httpx_mock.add_response(
        url="http://localhost:1/v1/2026-08-23?base=EUR&symbols=TRY",
        json={"amount": 1.0, "base": "EUR", "date": "2026-08-21", "rates": {"TRY": 40.5}}
    )
    
    response = client.get("/tools/convert?amount=100&from=EUR&to=TRY&date=2026-08-23")
    assert response.status_code == 200
    data = response.json()
    assert data["rate_date"] == "2026-08-21"  # Müşteriye bildirilen asıl gün
    assert data["asked_date"] == "2026-08-23"

def test_cache(httpx_mock):
    httpx_mock.add_response(
        url="http://localhost:1/v1/2026-08-28?base=EUR&symbols=TRY",
        json={"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 40.5}}
    )
    
    # İlk istekte httpx_mock'a gider
    response1 = client.get("/tools/convert?amount=10&from=EUR&to=TRY&date=2026-08-28")
    assert response1.status_code == 200
    
    # İkinci istekte cache'den gelmelidir, eğer API'ye giderse httpx_mock hata verir.
    response2 = client.get("/tools/convert?amount=10&from=EUR&to=TRY&date=2026-08-28")
    assert response2.status_code == 200

def test_upstream_not_found(httpx_mock):
    httpx_mock.add_response(
        url="http://localhost:1/v1/1990-01-01?base=EUR&symbols=TRY",
        status_code=404,
        json={"message": "not found"}
    )
    response = client.get("/tools/convert?amount=10&from=EUR&to=TRY&date=1990-01-01")
    assert response.status_code == 400
    assert response.json()["error"] == "not_found"

def test_upstream_error(httpx_mock):
    httpx_mock.add_response(
        url="http://localhost:1/v1/2026-08-28?base=EUR&symbols=TRY",
        status_code=500
    )
    response = client.get("/tools/convert?amount=10&from=EUR&to=TRY&date=2026-08-28")
    assert response.status_code == 502
    assert response.json()["error"] == "upstream_error"

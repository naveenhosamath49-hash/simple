from __future__ import annotations

import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.agmarknet import parse_arrival_date, parse_price, normalize_record


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_parse_arrival_date():
    """Verify arrival date parser handles Indian and ISO formats while rejecting invalid calendar dates."""
    d1 = parse_arrival_date("16/10/2026")
    assert d1 is not None
    assert d1.year == 2026 and d1.month == 10 and d1.day == 16

    d2 = parse_arrival_date("2026-10-16")
    assert d2 is not None
    assert d2.year == 2026 and d2.month == 10 and d2.day == 16

    assert parse_arrival_date("31/02/2026") is None
    assert parse_arrival_date("not-a-date") is None
    assert parse_arrival_date(None) is None


def test_parse_price():
    """Verify price parser handles commas, strings, numbers, and rejects invalid/negative values."""
    assert parse_price("1,800") == 1800.0
    assert parse_price(2400) == 2400.0
    assert parse_price(" 3250.50 ") == 3250.50
    assert parse_price("-50") is None
    assert parse_price("free") is None
    assert parse_price(None) is None


def test_normalize_record():
    """Verify record normalization accurately extracts fields and rejects invalid records."""
    valid_raw = {
        "state": "Karnataka",
        "district": "Mysuru",
        "market": "Mysore",
        "commodity": "Tomato",
        "variety": "Local",
        "grade": "FAQ",
        "arrival_date": "16/10/2026",
        "min_price": "1400",
        "max_price": "2400",
        "modal_price": "1800",
    }
    normalized = normalize_record(valid_raw)
    assert normalized is not None
    assert normalized["market"] == "Mysore"
    assert normalized["commodity"] == "Tomato"
    assert normalized["modal_price"] == 1800.0
    assert normalized["min_price"] == 1400.0
    assert normalized["max_price"] == 2400.0
    assert normalized["source"] == "data.gov.in Agmarknet"

    # Missing arrival_date
    invalid_raw = dict(valid_raw)
    invalid_raw["arrival_date"] = "invalid"
    assert normalize_record(invalid_raw) is None

    # Missing modal_price
    invalid_price = dict(valid_raw)
    invalid_price["modal_price"] = "N/A"
    assert normalize_record(invalid_price) is None


def test_healthz_endpoint(client):
    """Verify KrishiBhav liveness /healthz endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert data["database"] in ["connected", "disconnected"]


def test_market_prices_endpoint(client):
    """Verify market prices querying with filters and trend flag."""
    response = client.get("/api/v1/market-prices?commodity=Tomato&limit=10&includeTrend=true")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "total" in data
    assert isinstance(data["records"], list)
    assert len(data["records"]) > 0

    first_record = data["records"][0]
    assert first_record["commodity"].lower() == "tomato"
    assert "modal_price" in first_record
    assert "arrival_date" in first_record
    assert "trend" in first_record or "trend_direction" in first_record


def test_market_prices_history_endpoint(client):
    """Verify 7-day historical prices and trend metrics for charts."""
    response = client.get("/api/v1/market-prices/history?commodity=Tomato&market=Mysore")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Tomato"
    assert "history" in data
    assert "metrics" in data
    assert isinstance(data["history"], list)
    assert len(data["history"]) >= 2
    assert "average_modal_price" in data["metrics"]
    assert "trend_direction" in data["metrics"]


def test_distinct_commodities_and_markets(client):
    """Verify commodities and markets discovery endpoints."""
    r1 = client.get("/api/v1/commodities")
    assert r1.status_code == 200
    assert "commodities" in r1.json()
    assert "Tomato" in r1.json()["commodities"]

    r2 = client.get("/api/v1/markets")
    assert r2.status_code == 200
    assert "markets" in r2.json()
    markets = [m["market"] for m in r2.json()["markets"]]
    assert "Mysore" in markets or "Bangalore" in markets


def test_farmer_profile_lifecycle(client):
    """Verify farmer registration, profile update, and retrieval."""
    test_id = "farmer_test_123"
    payload = {
        "farmerId": test_id,
        "name": "Ramesh Kumar",
        "phone": "+919876543210",
        "preferredLanguage": "hi",
        "smsOptIn": True,
        "pushOptIn": False,
    }
    r = client.post("/api/v1/farmers", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["farmerId"] == test_id
    assert data["name"] == "Ramesh Kumar"
    assert data["preferredLanguage"] == "hi"
    assert data["smsOptIn"] is True

    # Retrieve profile
    get_res = client.get(f"/api/v1/farmers/{test_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Ramesh Kumar"


def test_alert_subscription_lifecycle(client):
    """Verify creating, listing, evaluating, and deactivating an alert."""
    farmer_id = "farmer_alert_test"
    # Create alert
    alert_payload = {
        "farmerId": farmer_id,
        "commodity": "Tomato",
        "market": "Mysore",
        "direction": "above",
        "threshold": 1700.0,
        "channel": "sms",
    }
    create_res = client.post("/api/v1/alerts", json=alert_payload)
    assert create_res.status_code == 200
    alert_data = create_res.json()
    alert_id = alert_data["alertId"]
    assert alert_data["active"] is True
    assert alert_data["threshold"] == 1700.0

    # List alerts
    list_res = client.get(f"/api/v1/alerts?farmerId={farmer_id}")
    assert list_res.status_code == 200
    alerts = list_res.json()
    assert any(a["alertId"] == alert_id for a in alerts)

    # Trigger evaluation
    eval_res = client.post("/api/v1/alerts/evaluate")
    assert eval_res.status_code == 200
    assert "evaluated_subscriptions" in eval_res.json()

    # Deactivate alert
    del_res = client.delete(f"/api/v1/alerts/{alert_id}?farmerId={farmer_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True


def test_weather_endpoint(client):
    """Verify agricultural weather and agromet advisory."""
    res = client.get("/api/v1/weather?district=Mysuru&state=Karnataka")
    assert res.status_code == 200
    data = res.json()
    assert data["district"].lower() in ["mysuru", "mysore"]
    assert "temperature" in data
    assert "humidity" in data
    assert "advisory" in data
    assert len(data["advisory"]) > 10


def test_grounded_ai_assistant_chat(client):
    """Verify grounded AI chat in English, Hindi, and Kannada, with citations."""
    # English query
    en_res = client.post("/api/v1/ai/chat", json={
        "query": "What is the modal price of Tomato in Mysore Mandi?",
        "language": "en"
    })
    assert en_res.status_code == 200
    en_data = en_res.json()
    assert en_data["grounded"] is True
    assert "citations" in en_data
    assert len(en_data["citations"]) > 0
    assert "Tomato" in en_data["response"]

    # Hindi query
    hi_res = client.post("/api/v1/ai/chat", json={
        "query": "मैसूर मंडी में टमाटर का क्या भाव है?",
        "language": "hi"
    })
    assert hi_res.status_code == 200
    hi_data = hi_res.json()
    assert hi_data["grounded"] is True
    assert "मैसूर" in hi_data["response"] or "टमाटर" in hi_data["response"]

    # Kannada query
    kn_res = client.post("/api/v1/ai/chat", json={
        "query": "ಮೈಸೂರು ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಟೊಮೇಟೊ ಬೆಲೆ ಎಷ್ಟಿದೆ?",
        "language": "kn"
    })
    assert kn_res.status_code == 200
    kn_data = kn_res.json()
    assert kn_data["grounded"] is True
    assert len(kn_data["response"]) > 0

    # Non-existent crop refusal test (Zero-fabrication guarantee)
    fake_crop_res = client.post("/api/v1/ai/chat", json={
        "query": "What is the price of DragonFruitSpecial in Mandya?",
        "language": "en"
    })
    assert fake_crop_res.status_code == 200
    # Must refuse to fabricate prices
    assert "do not have verified Agmarknet" in fake_crop_res.json()["response"]

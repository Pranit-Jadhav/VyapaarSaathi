from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to VyapaarSaathi API"}

def test_get_entries():
    response = client.get("/entries?vendor_id=test_123")
    assert response.status_code == 200
    assert "entries" in response.json()

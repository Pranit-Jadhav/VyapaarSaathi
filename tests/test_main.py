import main as main_module

from fastapi.testclient import TestClient

from services.settings import get_settings


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._limit = 100
        self._phone_filter = None

    def select(self, _fields):
        return self

    def order(self, _field, desc=False):
        self._rows = sorted(
            self._rows,
            key=lambda row: row.get("created_at", ""),
            reverse=bool(desc),
        )
        return self

    def limit(self, value):
        self._limit = int(value)
        return self

    def eq(self, field, value):
        if field == "phone":
            self._phone_filter = value
        return self

    def execute(self):
        rows = self._rows
        if self._phone_filter is not None:
            rows = [row for row in rows if row.get("phone") == self._phone_filter]
        return _FakeResult(rows[: self._limit])


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeQuery(self._rows)


def _configure_env(monkeypatch, validate_signature: str) -> None:
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth-token")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "service-role-key")
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURE", validate_signature)
    get_settings.cache_clear()


def test_read_root(monkeypatch):
    _configure_env(monkeypatch, validate_signature="false")
    client = TestClient(main_module.app)

    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["webhook"] == "/webhook"


def test_webhook_rejects_missing_signature(monkeypatch):
    _configure_env(monkeypatch, validate_signature="true")
    client = TestClient(main_module.app)

    payload = {
        "From": "whatsapp:+919999999999",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/fake-media",
        "MediaContentType0": "audio/ogg",
    }
    response = client.post("/webhook", data=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Missing Twilio signature"


def test_webhook_accepts_audio_when_signature_validation_disabled(monkeypatch):
    _configure_env(monkeypatch, validate_signature="false")
    client = TestClient(main_module.app)

    captured = {}

    def fake_process(sender: str, media_url: str) -> None:
        captured["sender"] = sender
        captured["media_url"] = media_url

    monkeypatch.setattr(main_module, "_process_and_reply", fake_process)

    payload = {
        "From": "whatsapp:+919999999999",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/fake-media",
        "MediaContentType0": "audio/ogg",
    }

    response = client.post("/webhook", data=payload)
    assert response.status_code == 200
    assert captured["sender"] == "whatsapp:+919999999999"
    assert captured["media_url"] == "https://api.twilio.com/fake-media"


def test_webhook_missing_audio_sends_prompt(monkeypatch):
    _configure_env(monkeypatch, validate_signature="false")
    client = TestClient(main_module.app)

    sent_messages = []

    def fake_send(to_phone: str, body: str, media_url=None):
        sent_messages.append((to_phone, body, media_url))
        return "SM123"

    monkeypatch.setattr(main_module, "send_whatsapp_reply", fake_send)

    payload = {
        "From": "whatsapp:+919999999999",
        "NumMedia": "0",
    }

    response = client.post("/webhook", data=payload)
    assert response.status_code == 200
    assert sent_messages
    assert "Voice note" in sent_messages[0][1]


def test_entries_compatibility_endpoint(monkeypatch):
    _configure_env(monkeypatch, validate_signature="false")
    client = TestClient(main_module.app)

    rows = [
        {
            "id": "1",
            "phone": "whatsapp:+919999999999",
            "amount": 500,
            "type": "income",
            "category": "tea",
            "description": "chai bechi",
            "audio_url": "https://example.com/audio1",
            "created_at": "2026-03-28T10:00:00Z",
        },
        {
            "id": "2",
            "phone": "whatsapp:+919999999999",
            "amount": 200,
            "type": "expense",
            "category": "milk",
            "description": "doodh kharida",
            "audio_url": "https://example.com/audio2",
            "created_at": "2026-03-28T09:00:00Z",
        },
    ]

    monkeypatch.setattr(main_module, "get_supabase", lambda: _FakeSupabase(rows))

    response = client.get("/entries?vendor_id=whatsapp:+919999999999&limit=7")
    assert response.status_code == 200
    payload = response.json()
    assert "entries" in payload
    assert len(payload["entries"]) == 2
    assert payload["entries"][0]["total_earned"] == 500.0
    assert payload["entries"][1]["total_spent"] == 200.0

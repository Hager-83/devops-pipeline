from app.app import app
import os


def test_home():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200


def test_health():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_home_body_contains_message_and_env():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.json["message"] == "Hello from devops-pipeline"
    # APP_ENV falls back to "dev" when unset
    assert response.json["env"] == os.getenv("APP_ENV", "dev")


def test_metrics_exposed():
    client = app.test_client()

    response = client.get("/metrics")

    assert response.status_code == 200
    # Prometheus exposition format always contains HELP lines
    assert b"# HELP" in response.data
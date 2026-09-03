import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["local_only"] is True
    assert data["runtime_api_tokens"] is False

def test_api_templates():
    res = client.get("/api/templates")
    assert res.status_code == 200
    templates = res.json()
    assert len(templates) >= 2
    ids = [t["id"] for t in templates]
    assert "electricity_bill" in ids
    assert "invoice" in ids

def test_api_documents_and_runs():
    res_docs = client.get("/api/documents")
    assert res_docs.status_code == 200
    assert isinstance(res_docs.json(), list)

    res_runs = client.get("/api/runs")
    assert res_runs.status_code == 200
    assert isinstance(res_runs.json(), list)

def test_api_benchmark_report():
    res = client.get("/api/benchmark/report")
    assert res.status_code == 200
    data = res.json()
    assert "overall_field_accuracy_pct" in data
    assert "document_accuracy_pct" in data

def test_frontend_root():
    res = client.get("/")
    assert res.status_code == 200
    assert "DocExtractor" in res.text

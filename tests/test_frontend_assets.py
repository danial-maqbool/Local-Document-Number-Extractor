"""
Tests for frontend static asset loading and MIME types.
Ensures that /, /ui, /style.css, and /app.js return HTTP 200 with proper Content-Type headers.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_frontend_root():
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "DocExtractor" in res.text

def test_frontend_ui_path():
    res = client.get("/ui")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "DocExtractor" in res.text

def test_frontend_ui_slash_path():
    res = client.get("/ui/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "DocExtractor" in res.text

def test_frontend_stylesheet():
    res = client.get("/style.css")
    assert res.status_code == 200
    assert "text/css" in res.headers.get("content-type", "")
    assert ":root" in res.text or "sidebar" in res.text

def test_frontend_javascript():
    res = client.get("/app.js")
    assert res.status_code == 200
    assert "application/javascript" in res.headers.get("content-type", "")
    assert "setupNavigation" in res.text or "state" in res.text

def test_frontend_ui_assets():
    res_css = client.get("/ui/style.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")

    res_js = client.get("/ui/app.js")
    assert res_js.status_code == 200
    assert "application/javascript" in res_js.headers.get("content-type", "")

def test_frontend_document_image():
    # Fetch first document from DB
    docs_res = client.get("/api/documents")
    assert docs_res.status_code == 200
    docs = docs_res.json()
    if docs:
        doc_id = docs[0]["id"]
        res = client.get(f"/api/documents/{doc_id}/image")
        assert res.status_code == 200
        assert "image/" in res.headers.get("content-type", "")

def test_frontend_excel_and_csv_exports():
    res_xlsx = client.get("/api/export/excel/electricity_bill")
    assert res_xlsx.status_code == 200
    assert "spreadsheetml" in res_xlsx.headers.get("content-type", "")

    res_csv = client.get("/api/export/csv/electricity_bill")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("content-type", "")

import json
import sys
from pathlib import Path

import pytest


TASK1_DIR = Path(__file__).resolve().parents[1]
APP_FILE_DIR = TASK1_DIR / "artifacts" / "app"
NOTEBOOK_PATH = TASK1_DIR / "course_feedback_generator.ipynb"
if str(APP_FILE_DIR) not in sys.path:
    sys.path.insert(0, str(APP_FILE_DIR))

from app import DATA_PATH, app, get_runtime_options


def _seed_feedback() -> list[dict]:
    return [
        {
            "id": 1,
            "course_name": "AI Software Engineering",
            "instructor_name": "Dr. Lee",
            "rating": 4,
            "category": "Teaching",
            "feedback_text": "The practical examples were helpful.",
            "sentiment": "positive",
            "created_at": "2026-05-27T12:00:00",
        }
    ]


def _write_seed_data() -> None:
    DATA_PATH.write_text(
        json.dumps(_seed_feedback(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_notebook_code() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    return "\n".join(code_cells)


@pytest.fixture(autouse=True)
def restore_feedback_file():
    original_contents = DATA_PATH.read_text(encoding="utf-8") if DATA_PATH.exists() else None
    yield
    if original_contents is None:
        if DATA_PATH.exists():
            DATA_PATH.unlink()
        return
    DATA_PATH.write_text(original_contents, encoding="utf-8")


def test_index_serves_single_page():
    client = app.test_client()

    response = client.get("/")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<title>Course Feedback Analysis System</title>" in body
    assert 'id="hero"' in body or "id='hero'" in body
    assert 'id="feedback-form"' in body or "id='feedback-form'" in body
    assert 'id="summary-section"' in body or "id='summary-section'" in body
    assert 'id="feedback-list"' in body or "id='feedback-list'" in body
    assert 'src="generated_hero.png"' in body or "src='generated_hero.png'" in body


def test_generated_hero_image_is_served():
    client = app.test_client()

    response = client.get("/generated_hero.png")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data


def test_health_endpoint_returns_expected_payload():
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "app": "course-feedback-analysis",
    }


def test_feedback_routes_read_and_append_entries():
    client = app.test_client()
    _write_seed_data()

    initial_response = client.get("/api/feedback")

    assert initial_response.status_code == 200
    assert len(initial_response.get_json()["feedback"]) == 1

    create_response = client.post(
        "/api/feedback",
        json={
            "course_name": "AI Software Engineering",
            "instructor_name": "Dr. Patel",
            "rating": 5,
            "category": "Engagement",
            "feedback_text": "Interactive labs made the content easier to follow.",
        },
    )

    assert create_response.status_code == 201
    payload = create_response.get_json()
    assert payload["message"] == "Feedback submitted successfully."
    assert payload["feedback"]["id"] == 2
    assert payload["feedback"]["sentiment"] == "positive"

    updated_feedback = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert len(updated_feedback) == 2
    assert updated_feedback[-1]["instructor_name"] == "Dr. Patel"


def test_create_feedback_accepts_rating_from_browser_form_payload():
    client = app.test_client()
    _write_seed_data()

    response = client.post(
        "/api/feedback",
        json={
            "course_name": "AI Software Engineering",
            "instructor_name": "Dr. Patel",
            "rating": "5",
            "category": "Engagement",
            "feedback_text": "Browser form payloads submit numeric fields as strings.",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["feedback"]["rating"] == 5
    assert payload["feedback"]["sentiment"] == "positive"

    updated_feedback = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert updated_feedback[-1]["rating"] == 5


def test_create_feedback_rejects_missing_required_fields():
    client = app.test_client()
    _write_seed_data()

    response = client.post(
        "/api/feedback",
        json={
            "course_name": "AI Software Engineering",
            "rating": 5,
            "feedback_text": "Missing some required fields.",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Missing required fields: category, instructor_name"
    }
    assert json.loads(DATA_PATH.read_text(encoding="utf-8")) == _seed_feedback()


def test_summary_endpoint_calculates_metrics_from_feedback():
    client = app.test_client()
    DATA_PATH.write_text(
        json.dumps(
            _seed_feedback()
            + [
                {
                    "id": 2,
                    "course_name": "AI Software Engineering",
                    "instructor_name": "Dr. Patel",
                    "rating": 2,
                    "category": "Assessment",
                    "feedback_text": "The assessment rubric was not clear enough.",
                    "sentiment": "negative",
                    "created_at": "2026-05-27T13:00:00",
                }
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    response = client.get("/api/summary")

    assert response.status_code == 200
    assert response.get_json() == {
        "total_feedback": 2,
        "average_rating": 3.0,
        "positive_ratio": 50.0,
        "top_category": "Teaching",
        "category_counts": {
            "Teaching": 1,
            "Assessment": 1,
        },
    }


def test_notebook_generates_backend_from_contract():
    payload = _load_notebook_code()

    assert "def generate_backend_code" in payload
    assert 'generate_backend_code(CONFIG, state["frozen_spec"], state["backend_contract"])' in payload
    assert 'write_text(APP_DIR / "app.py", APP_TEMPLATE)' not in payload


def test_notebook_generates_frontend_from_contract():
    payload = _load_notebook_code()

    assert "def generate_frontend_code" in payload
    assert 'generate_frontend_code(CONFIG, state["frozen_spec"], state["frontend_contract"])' in payload
    assert 'write_text(APP_DIR / "index.html", INDEX_TEMPLATE)' not in payload


def test_runtime_options_default_to_container_safe_values(monkeypatch):
    monkeypatch.delenv("FLASK_HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)

    assert get_runtime_options() == {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False,
    }


def test_runtime_options_read_flask_environment_overrides(monkeypatch):
    monkeypatch.setenv("FLASK_HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("FLASK_DEBUG", "yes")

    assert get_runtime_options() == {
        "host": "127.0.0.1",
        "port": 8080,
        "debug": True,
    }

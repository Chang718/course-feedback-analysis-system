import json
import sys
from pathlib import Path


TASK1_DIR = Path(__file__).resolve().parents[1]
if str(TASK1_DIR) not in sys.path:
    sys.path.insert(0, str(TASK1_DIR))

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "course_feedback_generator.ipynb"
FROZEN_SPEC_PATH = TASK1_DIR / "artifacts" / "spec" / "frozen_inception_spec.json"


def _load_code_sources() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    return "\n".join(code_cells)


def _slice_code_between(start_marker: str, end_marker: str) -> str:
    code = _load_code_sources()
    start = code.index(start_marker)
    end = code.index(end_marker, start)
    return code[start:end]


def _load_validation_namespace() -> dict:
    code = (
        "import json\n"
        "from utils import extract_data_field_names, find_forbidden_feature_violations\n"
    )
    code += _slice_code_between(
        "PROJECT_BRIEF = {",
        "def build_problem_messages",
    )
    code += "\n"
    code += _slice_code_between("def _collect_strings", "def freeze_inception_spec")
    namespace: dict = {}
    exec(code, namespace)
    return namespace


def test_task3_notebook_contains_inception_pipeline():
    code = _load_code_sources()

    assert "PROJECT_BRIEF" in code
    assert "problem_messages" in code
    assert "requirements_messages" in code
    assert "validate_required_fields" in code
    assert "validate_forbidden_features" in code
    assert "frozen_inception_spec.json" in code


def test_task3_notebook_includes_acceptance_business_rules_and_checkpoints():
    code = _load_code_sources()
    notebook_payload = NOTEBOOK_PATH.read_text(encoding="utf-8")

    assert "acceptance_criteria.json" in notebook_payload
    assert "business_rules.json" in notebook_payload
    assert "Checkpoint A" in notebook_payload
    assert "Checkpoint B" in notebook_payload
    assert '"acceptance_criteria": acceptance_criteria' in code
    assert '"business_rules": business_rules' in code


def test_task3_notebook_enforces_persona_role_schema():
    code = _load_code_sources()

    assert "Each persona must include the keys name, role, goals, and frustrations." in code
    assert "required_persona_keys" in code
    assert '"role"' in code


def test_task3_notebook_uses_retries_and_required_keys_for_llm_calls():
    code = _load_code_sources()

    assert 'max_attempts=3' in code
    assert 'required_keys={"problem_statement", "personas"}' in code
    assert (
        'required_keys={"requirements", "data_fields", "page_section_mapping", "endpoint_mapping", "user_stories"}'
        in code
    )


def test_task3_frozen_spec_fixture_contains_acceptance_business_rules_and_checkpoints():
    frozen_spec = json.loads(FROZEN_SPEC_PATH.read_text(encoding="utf-8"))

    assert "acceptance_criteria" in frozen_spec
    assert "business_rules" in frozen_spec
    assert "checkpoints" in frozen_spec["validation_report"]
    assert frozen_spec["validation_report"]["checkpoints"]["Checkpoint A"]["approved"] is True
    assert frozen_spec["validation_report"]["checkpoints"]["Checkpoint B"]["approved"] is True


def test_validate_required_fields_accepts_structured_field_definitions():
    namespace = _load_validation_namespace()

    report = namespace["validate_required_fields"](
        {
            "data_fields": [
                {"name": "course_name", "type": "string", "required": True},
                {"name": "instructor_name", "type": "string", "required": True},
                {"name": "rating", "type": "integer", "required": True},
                {"name": "category", "type": "string", "required": True},
                {"name": "feedback_text", "type": "string", "required": True},
            ]
        }
    )

    assert report["ok"] is True
    assert report["actual"] == [
        "category",
        "course_name",
        "feedback_text",
        "instructor_name",
        "rating",
    ]


def test_validate_required_fields_accepts_field_name_objects():
    namespace = _load_validation_namespace()

    report = namespace["validate_required_fields"](
        {
            "data_fields": [
                {"field_name": "course_name", "type": "string"},
                {"field_name": "instructor_name", "type": "string"},
                {"field_name": "rating", "type": "integer"},
                {"field_name": "category", "type": "string"},
                {"field_name": "feedback_text", "type": "text"},
            ]
        }
    )

    assert report["ok"] is True
    assert report["actual"] == [
        "category",
        "course_name",
        "feedback_text",
        "instructor_name",
        "rating",
    ]


def test_validate_forbidden_features_ignores_negated_scope_statements():
    namespace = _load_validation_namespace()

    report = namespace["validate_forbidden_features"](
        {
            "problem_statement": "No login system or multi-role access control is required.",
        },
        {
            "requirements": [
                "No runtime LLM analysis or RAG pipelines should appear in the deployed app."
            ]
        },
    )

    assert report == {"ok": True, "violations": []}


def test_validate_forbidden_features_accepts_shall_not_include_requirements():
    namespace = _load_validation_namespace()

    report = namespace["validate_forbidden_features"](
        {
            "problem_statement": "A simple single-page course feedback website is required.",
        },
        {
            "requirements": [
                (
                    "The system shall not include any authentication, multi-role access, "
                    "LLM analysis, multi-page navigation, RAG pipelines, or multi-agent collaboration."
                )
            ],
            "user_stories": [
                {
                    "story": "As an instructor, I want a single-page workflow so that I do not navigate to another page."
                }
            ],
        },
    )

    assert report == {"ok": True, "violations": []}


def test_validate_forbidden_features_accepts_forbidden_scope_explanations():
    namespace = _load_validation_namespace()

    report = namespace["validate_forbidden_features"](
        {
            "problem_statement": "A simple single-page course feedback website is required.",
        },
        {
            "requirements": [
                "Store feedback in-memory (simple list) due to forbidden complex database schema."
            ]
        },
    )

    assert report == {"ok": True, "violations": []}


def test_validate_forbidden_features_ignores_mirrored_forbidden_feature_metadata():
    namespace = _load_validation_namespace()

    report = namespace["validate_forbidden_features"](
        {
            "problem_statement": "A simple single-page course feedback website is required.",
        },
        {
            "requirements": {
                "domain": "course feedback analysis",
                "forbidden_features": [
                    "login system",
                    "multi-role access control",
                    "runtime llm analysis",
                    "multi-page navigation",
                    "complex database schema",
                    "rag pipelines",
                    "multi-agent collaboration loops",
                ],
            },
            "user_stories": [
                {
                    "story": "As a student, I want to submit feedback without creating an account."
                }
            ],
        },
    )

    assert report == {"ok": True, "violations": []}


def test_validate_forbidden_features_ignores_nested_forbidden_feature_metadata():
    namespace = _load_validation_namespace()

    report = namespace["validate_forbidden_features"](
        {
            "problem_statement": "A simple single-page course feedback website is required.",
        },
        {
            "requirements": [
                {
                    "summary": "Keep the app lightweight and easy to run.",
                    "constraints": {
                        "forbidden_features": [
                            "login system",
                            "multi-role access control",
                        ]
                    },
                }
            ],
            "user_stories": [
                {
                    "story": "As a student, I want to submit feedback without creating an account."
                }
            ],
        },
    )

    assert report == {"ok": True, "violations": []}


def test_task3_frozen_spec_preserves_feedback_get_and_post_methods():
    frozen_spec = json.loads(FROZEN_SPEC_PATH.read_text(encoding="utf-8"))

    endpoint_mapping = frozen_spec["endpoint_mapping"]
    assert isinstance(endpoint_mapping, list)

    feedback_methods = sorted(
        item["method"]
        for item in endpoint_mapping
        if item["path"] == "/api/feedback"
    )
    assert feedback_methods == ["GET", "POST"]

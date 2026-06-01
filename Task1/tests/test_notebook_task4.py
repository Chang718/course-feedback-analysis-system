import json
from pathlib import Path


NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "course_feedback_generator.ipynb"
SPEC_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "spec"
FROZEN_SPEC_PATH = SPEC_DIR / "frozen_inception_spec.json"


def _load_code_sources() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    return "\n".join(code_cells)


def test_task4_notebook_contains_langgraph_construction_pipeline():
    code = _load_code_sources()

    assert "TypedDict" in code
    assert "StateGraph" in code
    assert "class BuildState" in code
    assert '"frozen_spec"' in code
    assert '"api_spec"' in code
    assert '"ui_spec"' in code
    assert '"uml_source"' in code
    assert '"image_prompt"' in code
    assert "def design_system" in code
    assert "def generate_artifacts" in code
    assert 'graph.add_node("design_system", design_system)' in code
    assert 'graph.add_node("generate_artifacts", generate_artifacts)' in code
    assert "compiled_graph = graph.compile()" in code
    assert "compiled_graph.invoke" in code


def test_task4_notebook_builds_and_exports_contract_artifacts():
    code = _load_code_sources()
    notebook_payload = NOTEBOOK_PATH.read_text(encoding="utf-8")

    assert "backend_contract.json" in notebook_payload
    assert "frontend_contract.json" in notebook_payload
    assert "uml_contract.json" in notebook_payload
    assert "def build_backend_contract" in code
    assert "def build_frontend_contract" in code
    assert "def build_uml_contract" in code
    assert 'write_json(SPEC_DIR / "backend_contract.json", state["backend_contract"])' in code
    assert 'write_json(SPEC_DIR / "frontend_contract.json", state["frontend_contract"])' in code
    assert 'write_json(SPEC_DIR / "uml_contract.json", state["uml_contract"])' in code


def test_task4_notebook_normalizes_persona_roles_for_uml_contract():
    code = _load_code_sources()

    assert 'persona.get("role")' in code
    assert 'persona.get("title")' in code


def test_task4_notebook_requires_backend_to_serve_external_frontend_file():
    code = _load_code_sources()

    assert "Return Python source code only." in code
    assert "Serve the generated index.html file for the root route." in code
    assert "Do not embed HTML templates inside app.py." in code


def test_task4_notebook_validates_frontend_against_feedback_payload_shape():
    code = _load_code_sources()

    assert 'feedbackData.feedback' in code
    assert "Missing feedback collection reference: feedbackData.feedback" in code


def test_task4_notebook_retries_upon_step6_json_boundary_failures():
    code = _load_code_sources()

    assert 'required_keys={"use_case", "activity"}' in code
    assert 'required_keys={"artifact"}' in code
    assert "max_attempts=3" in code


def test_task4_backend_contract_tracks_runtime_symbols_and_summary_semantics():
    frozen_spec = json.loads(FROZEN_SPEC_PATH.read_text(encoding="utf-8"))
    backend_contract = json.loads((SPEC_DIR / "backend_contract.json").read_text(encoding="utf-8"))

    assert backend_contract["routes"] == frozen_spec["project_brief"]["required_endpoints"]
    assert backend_contract["data_file"] == "seed_feedback.json"
    assert backend_contract["index_file"] == "index.html"
    assert backend_contract["data_path_symbol"] == "DATA_PATH"
    assert backend_contract["runtime_options_symbol"] == "get_runtime_options"
    assert backend_contract["summary_ratio_scale"] == "percentage_0_100"
    assert backend_contract["persistence_mode"] == "file_backed_per_request"
    assert backend_contract["runtime_defaults"] == {
        "host": "0.0.0.0",
        "host_env": "FLASK_HOST",
        "port_env": "PORT",
        "port": 5000,
        "debug_env": "FLASK_DEBUG",
        "debug": False,
    }
    assert backend_contract["success_message"] == "Feedback submitted successfully."
    assert backend_contract["missing_fields_prefix"] == "Missing required fields:"
    assert backend_contract["category_counts_mode"] == "observed_only"


def test_task4_notebook_backend_prompt_requires_runtime_symbols_and_percentage_ratio():
    code = _load_code_sources()

    assert "Expose DATA_PATH as a pathlib.Path constant." in code
    assert "Define get_runtime_options() to read host, port, and debug settings." in code
    assert "Read the runtime host from FLASK_HOST and debug mode from FLASK_DEBUG." in code
    assert "Read and write feedback directly from seed_feedback.json for each request; do not keep a module-level feedback cache." in code
    assert "Return positive_ratio as a percentage between 0 and 100." in code
    assert "Default runtime options to host 0.0.0.0, PORT 5000, and debug False." in code
    assert 'Return GET /api/health as {"status": "ok", "app": "course-feedback-analysis"}.' in code
    assert "Return the exact success message Feedback submitted successfully." in code
    assert "Format missing required-field errors as Missing required fields: ... with alphabetical field ordering." in code
    assert "Return category_counts with observed categories only." in code
    assert "Accept browser-style string ratings by converting them to integers before backend validation." in code


def test_task4_frontend_contract_tracks_submission_title():
    frontend_contract = json.loads((SPEC_DIR / "frontend_contract.json").read_text(encoding="utf-8"))

    assert frontend_contract["page_title"] == "Course Feedback Analysis System"


def test_task4_notebook_frontend_prompt_requires_submission_title():
    code = _load_code_sources()

    assert "Use the page title Course Feedback Analysis System." in code
    assert "Convert the rating field to a number before POST /api/feedback." in code


def test_task4_notebook_explicitly_retries_backend_and_frontend_generation():
    code = _load_code_sources()

    backend_start = code.index("def generate_backend_code")
    frontend_start = code.index("def generate_frontend_code")
    validation_start = code.index("def validate_backend_artifact")

    backend_block = code[backend_start:frontend_start]
    frontend_block = code[frontend_start:validation_start]

    assert "max_attempts=3" in backend_block
    assert "max_attempts=3" in frontend_block


def test_task4_backend_prompt_requires_flexible_debug_parsing():
    code = _load_code_sources()

    assert "Parse FLASK_DEBUG flexibly so true, 1, and yes all enable debug mode." in code


def test_task4_contract_fixtures_exist_and_align_with_frozen_spec():
    frozen_spec = json.loads(FROZEN_SPEC_PATH.read_text(encoding="utf-8"))
    backend_contract = json.loads((SPEC_DIR / "backend_contract.json").read_text(encoding="utf-8"))
    frontend_contract = json.loads((SPEC_DIR / "frontend_contract.json").read_text(encoding="utf-8"))
    uml_contract = json.loads((SPEC_DIR / "uml_contract.json").read_text(encoding="utf-8"))

    assert backend_contract["routes"] == frozen_spec["project_brief"]["required_endpoints"]
    assert backend_contract["required_fields"] == frozen_spec["project_brief"]["required_fields"]
    assert frontend_contract["sections"] == frozen_spec["project_brief"]["required_sections"]
    assert frontend_contract["category_enum"] == frozen_spec["business_rules"]["category_enum"]
    assert uml_contract["actors"] == [persona["role"] for persona in frozen_spec["personas"]]
    assert uml_contract["user_stories"] == frozen_spec["user_stories"]

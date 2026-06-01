import json
from pathlib import Path


NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "course_feedback_generator.ipynb"


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


def _load_render_helper_namespace() -> dict:
    render_code = _slice_code_between(
        "def resolve_image_download_url",
        "def render_build_artifacts",
    )
    namespace: dict = {}
    exec(render_code, namespace)
    return namespace


def _load_validation_namespace() -> dict:
    code = _load_code_sources()
    start = code.index("def validate_backend_artifact")
    end = code.index("def generate_artifacts")
    namespace: dict = {}
    exec(code[start:end], namespace)
    return namespace


def _load_uml_namespace() -> dict:
    code = _load_code_sources()
    start = code.index("def build_deterministic_uml_source")
    end = code.index("def design_system")
    namespace: dict = {"json": json}
    exec(code[start:end], namespace)
    return namespace


def test_task5_notebook_contains_render_and_validation_pipeline():
    code = _load_code_sources()

    assert "generate_qwen_image" in code
    assert "download_image" in code
    assert "render_plantuml_diagram" in code
    assert "def resolve_image_download_url" in code
    assert "def render_uml_diagrams" in code
    assert "def render_build_artifacts" in code
    assert 'DESIGN_DIR / "use_case_diagram.puml"' in code
    assert 'DESIGN_DIR / "activity_diagram.puml"' in code
    assert 'DESIGN_DIR / "use_case_diagram.png"' in code
    assert 'DESIGN_DIR / "activity_diagram.png"' in code
    assert 'write_text(SPEC_DIR / "api_spec.json"' in code or 'write_json(SPEC_DIR / "api_spec.json"' in code
    assert 'write_text(SPEC_DIR / "ui_spec.json"' in code or 'write_json(SPEC_DIR / "ui_spec.json"' in code
    assert 'write_text(SPEC_DIR / "uml_source.json"' in code or 'write_json(SPEC_DIR / "uml_source.json"' in code
    assert 'write_text(SPEC_DIR / "image_prompt.txt"' in code
    assert 'write_json(SPEC_DIR / "build_report.json"' in code
    assert 'write_text(APP_DIR / "app.py"' in code
    assert 'write_text(APP_DIR / "index.html"' in code
    assert 'write_text(APP_DIR / "requirements.txt"' in code
    assert 'write_text(APP_DIR / "Dockerfile"' in code
    assert 'write_json(APP_DIR / "seed_feedback.json"' in code
    assert "SEED_FEEDBACK =" in code
    assert "REQUIREMENTS_TEMPLATE =" in code
    assert "DOCKERFILE_TEMPLATE =" in code
    assert "FALLBACK_HERO_IMAGE_URL =" in code
    assert "generated_files = [" in code
    assert "optional_generated_files = [" in code
    assert "missing_optional_outputs" in code
    assert "missing_outputs" in code


def test_task5_notebook_uses_contract_driven_uml_generation():
    code = _load_code_sources()

    assert "def build_deterministic_uml_source" in code
    assert "def generate_uml_source_from_contract" in code
    assert "def validate_uml_source" in code
    assert 'for index, actor_name in enumerate(uml_contract["actors"], start=1):' in code
    assert 'for step in uml_contract["workflow_steps"]:' in code
    assert 'generate_uml_source_from_contract(CONFIG, state["uml_contract"])' in code
    assert 'if payload_findings:' in code
    assert 'return build_deterministic_uml_source(uml_contract)' in code
    assert "Each UML string must start with @startuml and end with @enduml." in code
    assert 'uml_findings = validate_uml_source(uml_source, state["uml_contract"])' in code


def test_generate_uml_source_from_contract_falls_back_after_transport_error():
    namespace = _load_uml_namespace()
    deterministic_result = {
        "use_case": "@startuml\nactor Student\n@enduml",
        "activity": "@startuml\nstart\nstop\n@enduml",
    }
    calls = {"count": 0}

    def fake_call_deepseek_json(**kwargs):
        calls["count"] += 1
        raise RuntimeError("network interrupted")

    namespace["call_deepseek_json"] = fake_call_deepseek_json
    namespace["validate_uml_source"] = lambda payload, contract: []
    namespace["build_deterministic_uml_source"] = lambda contract: deterministic_result

    result = namespace["generate_uml_source_from_contract"](
        {"deepseek_model": "deepseek-v4-flash", "deepseek_api_key": "test-key"},
        {
            "actors": ["Student"],
            "user_stories": [{"story": "As a student, I want to submit feedback."}],
            "workflow_steps": ["Open website", "Submit feedback"],
        },
    )

    assert result == deterministic_result
    assert calls["count"] == 1


def test_notebook_task5_includes_validation_and_reflection():
    code = _load_code_sources()

    assert "def validate_backend_artifact" in code
    assert "def validate_frontend_artifact" in code
    assert "def run_narrow_reflection" in code
    assert 'validate_backend_artifact(backend_code, state["backend_contract"])' in code
    assert 'validate_frontend_artifact(frontend_code, state["frontend_contract"])' in code
    assert 'run_narrow_reflection(CONFIG, "backend", backend_code, state["backend_contract"], backend_findings)' in code
    assert 'run_narrow_reflection(CONFIG, "frontend", frontend_code, state["frontend_contract"], frontend_findings)' in code


def test_validate_frontend_artifact_accepts_kebab_case_section_ids():
    namespace = _load_validation_namespace()

    findings = namespace["validate_frontend_artifact"](
        '<section id="hero"></section><section id="summary-section"></section><section id="feedback-list"></section>',
        {
            "sections": ["hero", "summary", "feedback_list"],
            "image_file": "generated_hero.png",
        },
    )

    assert findings == ["Missing generated hero image reference."]


def test_validate_backend_artifact_flags_missing_runtime_contract_symbols():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "from flask import Flask\napp = Flask(__name__)\n",
        {
            "routes": ["/api/health"],
            "required_fields": ["course_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
            "data_path_symbol": "DATA_PATH",
            "runtime_options_symbol": "get_runtime_options",
            "summary_ratio_scale": "percentage_0_100",
            "persistence_mode": "file_backed_per_request",
            "runtime_defaults": {
                "host": "0.0.0.0",
                "host_env": "FLASK_HOST",
                "port_env": "PORT",
                "port": 5000,
                "debug_env": "FLASK_DEBUG",
                "debug": False,
            },
            "success_message": "Feedback submitted successfully.",
            "missing_fields_prefix": "Missing required fields:",
            "category_counts_mode": "observed_only",
        },
    )

    assert "Missing DATA_PATH symbol: DATA_PATH" in findings
    assert "Missing runtime options helper: get_runtime_options" in findings
    assert "Missing percentage positive_ratio implementation." in findings
    assert "Missing runtime default host: 0.0.0.0" in findings
    assert "Missing runtime host environment variable: FLASK_HOST" in findings
    assert "Missing runtime port environment variable: PORT" in findings
    assert "Missing runtime debug environment variable: FLASK_DEBUG" in findings
    assert "Missing runtime debug default: False" in findings
    assert "Missing success message: Feedback submitted successfully." in findings
    assert "Missing required-fields error prefix: Missing required fields:" in findings


def test_validate_backend_artifact_flags_module_level_feedback_cache():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "feedback_list = []\n"
        "@app.route('/api/feedback')\n"
        "def get_feedback():\n"
        "    return jsonify({'feedback': feedback_list})\n",
        {
            "routes": ["/api/feedback"],
            "required_fields": ["course_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
            "persistence_mode": "file_backed_per_request",
        },
    )

    assert "Backend must read feedback from seed_feedback.json per request, not from a module-level cache." in findings


def test_validate_backend_artifact_flags_send_static_file_root_route():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "def index():\n    return app.send_static_file('index.html')\n",
        {
            "routes": ["/api/health"],
            "required_fields": ["course_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
        },
    )

    assert "Backend root route must serve index.html from the app directory, not Flask static." in findings


def test_validate_backend_artifact_flags_missing_generated_hero_image_route():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "from flask import send_from_directory\n"
        "@app.route('/')\n"
        "def index():\n"
        "    return send_from_directory(app.root_path, 'index.html')\n",
        {
            "routes": ["/api/health"],
            "required_fields": ["course_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
            "image_file": "generated_hero.png",
        },
    )

    assert "Backend must serve generated hero image from the app directory." in findings


def test_validate_backend_artifact_flags_strict_debug_string_comparison():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "def get_runtime_options():\n"
        "    return {\n"
        "        'host': os.environ.get('FLASK_HOST', '0.0.0.0'),\n"
        "        'port': int(os.environ.get('PORT', 5000)),\n"
        "        'debug': os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'\n"
        "    }\n",
        {
            "routes": ["/api/health"],
            "required_fields": ["course_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
            "runtime_defaults": {
                "host": "0.0.0.0",
                "host_env": "FLASK_HOST",
                "port_env": "PORT",
                "port": 5000,
                "debug_env": "FLASK_DEBUG",
                "debug": False,
            },
        },
    )

    assert "Runtime debug parsing must accept true/1/yes values, not only the exact string true." in findings


def test_validate_backend_artifact_flags_strict_debug_string_comparison_with_capitalised_default():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "def get_runtime_options():\n"
        "    return {\n"
        "        'host': os.environ.get('FLASK_HOST', '0.0.0.0'),\n"
        "        'port': int(os.environ.get('PORT', 5000)),\n"
        "        'debug': os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'\n"
        "    }\n",
        {
            "routes": ["/api/health"],
            "required_fields": ["course_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
            "runtime_defaults": {
                "host": "0.0.0.0",
                "host_env": "FLASK_HOST",
                "port_env": "PORT",
                "port": 5000,
                "debug_env": "FLASK_DEBUG",
                "debug": False,
            },
        },
    )

    assert "Runtime debug parsing must accept true/1/yes values, not only the exact string true." in findings


def test_validate_backend_artifact_flags_incorrect_health_status_value():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "from flask import jsonify\n"
        "@app.route('/api/health', methods=['GET'])\n"
        "def health():\n"
        "    return jsonify({'status': 'healthy', 'app': 'course-feedback-analysis'})\n",
        {
            "routes": ["/api/health"],
            "required_fields": ["course_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
            "health_app_name": "course-feedback-analysis",
            "health_status": "ok",
        },
    )

    assert "Health endpoint must return status ok." in findings


def test_validate_backend_artifact_flags_missing_string_rating_normalisation():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "def post_feedback():\n"
        "    data = request.get_json() or {}\n"
        "    rating = data.get('rating')\n"
        "    if not isinstance(rating, int) or rating < 1 or rating > 5:\n"
        "        return jsonify({'error': 'Rating must be an integer between 1 and 5.'}), 400\n",
        {
            "routes": ["/api/feedback"],
            "required_fields": ["course_name", "instructor_name", "rating", "category", "feedback_text"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
        },
    )

    assert "Backend must normalise browser-style string ratings before validating the rating range." in findings


def test_validate_backend_artifact_flags_list_repr_missing_fields_error():
    namespace = _load_validation_namespace()

    findings = namespace["validate_backend_artifact"](
        "required_fields = ['course_name', 'instructor_name']\n"
        "missing = sorted([field for field in required_fields if field not in data])\n"
        "return jsonify({'error': f'Missing required fields: {missing}'}), 400\n",
        {
            "routes": ["/api/feedback"],
            "required_fields": ["course_name", "instructor_name"],
            "index_file": "index.html",
            "data_file": "seed_feedback.json",
            "missing_fields_prefix": "Missing required fields:",
        },
    )

    assert "Missing required-fields error must join field names into plain text, not a Python list representation." in findings


def test_validate_frontend_artifact_flags_missing_submission_title():
    namespace = _load_validation_namespace()

    findings = namespace["validate_frontend_artifact"](
        '<html><head><title>Course Feedback</title></head><body><section id="hero"></section><section id="summary-section"></section><section id="feedback-list"></section><img src="generated_hero.png"></body></html>',
        {
            "sections": ["hero", "summary", "feedback_list"],
            "required_dom_ids": ["hero", "summary-section", "feedback-list"],
            "image_file": "generated_hero.png",
            "feedback_collection_reference": "feedbackData.feedback",
            "page_title": "Course Feedback Analysis System",
        },
    )

    assert "Missing page title: Course Feedback Analysis System" in findings


def test_validate_frontend_artifact_flags_feedback_payload_shape_mismatch():
    namespace = _load_validation_namespace()

    findings = namespace["validate_frontend_artifact"](
        """
        <html>
          <head><title>Course Feedback Analysis System</title></head>
          <body>
            <section id="hero"></section>
            <section id="summary-section"></section>
            <section id="feedback-list"></section>
            <img src="generated_hero.png">
            <script>
              let feedbackData = { feedback: [] };
              feedbackData.feedback = data;
              if (data.length === 0) {}
              data.forEach(item => console.log(item));
            </script>
          </body>
        </html>
        """,
        {
            "sections": ["hero", "summary", "feedback_list"],
            "required_dom_ids": ["hero", "summary-section", "feedback-list"],
            "image_file": "generated_hero.png",
            "feedback_collection_reference": "feedbackData.feedback",
            "page_title": "Course Feedback Analysis System",
        },
    )

    assert "Frontend must iterate over feedbackData.feedback, not the raw API response object." in findings


def test_validate_frontend_artifact_flags_missing_numeric_rating_conversion():
    namespace = _load_validation_namespace()

    findings = namespace["validate_frontend_artifact"](
        """
        <html>
          <head><title>Course Feedback Analysis System</title></head>
          <body>
            <section id="hero"></section>
            <section id="summary-section"></section>
            <section id="feedback-list"></section>
            <img src="generated_hero.png">
            <script>
              const formData = new FormData(form);
              const payload = {};
              formData.forEach((value, key) => { payload[key] = value; });
            </script>
          </body>
        </html>
        """,
        {
            "sections": ["hero", "summary", "feedback_list"],
            "required_dom_ids": ["hero", "summary-section", "feedback-list"],
            "image_file": "generated_hero.png",
            "feedback_collection_reference": "feedbackData.feedback",
            "page_title": "Course Feedback Analysis System",
        },
    )

    assert "Frontend must convert the rating field to a number before POST /api/feedback." in findings


def test_resolve_image_download_url_reads_dashscope_choices_payload():
    namespace = _load_render_helper_namespace()

    image_url = namespace["resolve_image_download_url"](
        {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.com/generated-choice-image.png"}
                            ]
                        }
                    }
                ]
            }
        }
    )

    assert image_url == "https://example.com/generated-choice-image.png"

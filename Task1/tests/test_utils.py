import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


TASK1_DIR = Path(__file__).resolve().parents[1]
if str(TASK1_DIR) not in sys.path:
    sys.path.insert(0, str(TASK1_DIR))

import utils


class _ImageHandler(BaseHTTPRequestHandler):
    payload = b"fake-image-bytes"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        return


@pytest.fixture
def image_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ImageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/hero.png"
    finally:
        server.shutdown()
        thread.join()


def test_load_env_config_reads_defaults_and_project_env(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    nested_dir = project_root / "notebooks"
    nested_dir.mkdir(parents=True)
    (project_root / ".env").write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=deepseek-test-key",
                "DASHSCOPE_API_KEY=qwen-test-key",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(nested_dir)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("QWEN_IMAGE_MODEL", raising=False)

    config = utils.load_env_config()

    assert config["deepseek_api_key"] == "deepseek-test-key"
    assert config["dashscope_api_key"] == "qwen-test-key"
    assert config["deepseek_model"] == "deepseek-v4-flash"
    assert config["qwen_image_model"] == "qwen-image-2.0-pro"


def test_call_deepseek_json_returns_parsed_json(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"problem_statement": "Feedback analysis app"}
                            )
                        }
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(utils.requests, "post", fake_post)

    result = utils.call_deepseek_json(
        messages=[{"role": "user", "content": "return JSON"}],
        model="deepseek-v4-flash",
        api_key="deepseek-test-key",
    )

    assert result == {"problem_statement": "Feedback analysis app"}
    assert captured["headers"]["Authorization"] == "Bearer deepseek-test-key"
    assert captured["json"]["response_format"] == {"type": "json_object"}


def test_call_deepseek_json_extracts_json_from_code_fence(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "```json\n{\"artifact\": \"print('ok')\"}\n```"
                        }
                    }
                ]
            }

    monkeypatch.setattr(utils.requests, "post", lambda *args, **kwargs: FakeResponse())

    result = utils.call_deepseek_json(
        messages=[{"role": "user", "content": "return JSON"}],
        model="deepseek-v4-flash",
        api_key="deepseek-test-key",
    )

    assert result == {"artifact": "print('ok')"}


def test_call_deepseek_json_extracts_first_json_object_when_extra_text_follows(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "{\"artifact\": \"print('ok')\"}\nAdditional explanation"
                        }
                    }
                ]
            }

    monkeypatch.setattr(utils.requests, "post", lambda *args, **kwargs: FakeResponse())

    result = utils.call_deepseek_json(
        messages=[{"role": "user", "content": "return JSON"}],
        model="deepseek-v4-flash",
        api_key="deepseek-test-key",
    )

    assert result == {"artifact": "print('ok')"}


def test_call_deepseek_json_retries_after_invalid_json_response(monkeypatch):
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"requirements": ["ok"], "data_fields": [}'
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "requirements": ["ok"],
                                    "data_fields": {"course_name": {"type": "string"}},
                                    "page_section_mapping": {"hero": ["headline"]},
                                    "endpoint_mapping": {"/api/summary": ["GET"]},
                                    "user_stories": ["As a student, I can submit feedback."],
                                }
                            )
                        }
                    }
                ]
            },
        ]
    )

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(*args, **kwargs):
        return FakeResponse(next(responses))

    monkeypatch.setattr(utils.requests, "post", fake_post)

    result = utils.call_deepseek_json(
        messages=[{"role": "user", "content": "return JSON"}],
        model="deepseek-v4-flash",
        api_key="deepseek-test-key",
        required_keys={
            "requirements",
            "data_fields",
            "page_section_mapping",
            "endpoint_mapping",
            "user_stories",
        },
        max_attempts=2,
    )

    assert sorted(result) == [
        "data_fields",
        "endpoint_mapping",
        "page_section_mapping",
        "requirements",
        "user_stories",
    ]


def test_call_deepseek_json_retries_when_required_keys_are_missing(monkeypatch):
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "requirements": ["ok"],
                                    "data_fields": {"course_name": {"type": "string"}},
                                }
                            )
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "requirements": ["ok"],
                                    "data_fields": {"course_name": {"type": "string"}},
                                    "page_section_mapping": {"hero": ["headline"]},
                                    "endpoint_mapping": {"/api/summary": ["GET"]},
                                    "user_stories": ["As a student, I can submit feedback."],
                                }
                            )
                        }
                    }
                ]
            },
        ]
    )

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(*args, **kwargs):
        return FakeResponse(next(responses))

    monkeypatch.setattr(utils.requests, "post", fake_post)

    result = utils.call_deepseek_json(
        messages=[{"role": "user", "content": "return JSON"}],
        model="deepseek-v4-flash",
        api_key="deepseek-test-key",
        required_keys={
            "requirements",
            "data_fields",
            "page_section_mapping",
            "endpoint_mapping",
            "user_stories",
        },
        max_attempts=2,
    )

    assert result["user_stories"] == ["As a student, I can submit feedback."]


def test_call_deepseek_json_retries_after_chunked_encoding_error(monkeypatch):
    attempts = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"artifact": "print('ok')"})
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise utils.requests.exceptions.ChunkedEncodingError(
                "Response ended prematurely"
            )
        return FakeResponse()

    monkeypatch.setattr(utils.requests, "post", fake_post)

    result = utils.call_deepseek_json(
        messages=[{"role": "user", "content": "return JSON"}],
        model="deepseek-v4-flash",
        api_key="deepseek-test-key",
        required_keys={"artifact"},
        max_attempts=2,
    )

    assert result == {"artifact": "print('ok')"}
    assert attempts["count"] == 2


def test_generate_qwen_image_returns_api_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output": {
                    "results": [
                        {"url": "https://example.com/generated-image.png"},
                    ]
                }
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(utils.requests, "post", fake_post)

    result = utils.generate_qwen_image(
        prompt="Create a clean hero image for a course feedback dashboard",
        api_key="qwen-test-key",
    )

    assert result["output"]["results"][0]["url"].endswith(".png")
    assert captured["headers"]["Authorization"] == "Bearer qwen-test-key"
    assert captured["json"]["parameters"]["size"] == "1024*1024"


def test_generate_qwen_image_uses_china_endpoint_when_region_is_cn(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output": {"results": [{"url": "https://example.com/cn-image.png"}]}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(utils.requests, "post", fake_post)

    utils.generate_qwen_image(
        prompt="Generate an academic dashboard hero image",
        api_key="qwen-test-key",
        region="cn",
    )

    assert (
        captured["url"]
        == "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )


def test_generate_qwen_image_retries_cn_after_intl_invalid_api_key(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise utils.requests.HTTPError(
                    f"{self.status_code} error",
                    response=self,
                )

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        if "dashscope-intl" in url:
            return FakeResponse(
                401,
                {"code": "InvalidApiKey", "message": "Invalid API-key provided."},
            )
        return FakeResponse(
            200,
            {"output": {"results": [{"url": "https://example.com/cn-image.png"}]}},
        )

    monkeypatch.setattr(utils.requests, "post", fake_post)

    result = utils.generate_qwen_image(
        prompt="Generate an academic dashboard hero image",
        api_key="qwen-test-key",
    )

    assert result["output"]["results"][0]["url"].endswith(".png")
    assert calls == [
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    ]


def test_load_env_config_reads_dashscope_region_and_endpoint(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    env_file = project_root / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=deepseek-test-key",
                "DASHSCOPE_API_KEY=qwen-test-key",
                "DASHSCOPE_REGION=cn",
                "DASHSCOPE_IMAGE_ENDPOINT=https://example.com/custom-endpoint",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_REGION", raising=False)
    monkeypatch.delenv("DASHSCOPE_IMAGE_ENDPOINT", raising=False)

    config = utils.load_env_config(env_file)

    assert config["dashscope_region"] == "cn"
    assert config["dashscope_image_endpoint"] == "https://example.com/custom-endpoint"


def test_write_helpers_create_parent_directories(tmp_path):
    json_path = tmp_path / "artifacts" / "spec" / "requirements.json"
    text_path = tmp_path / "artifacts" / "spec" / "problem_statement.md"

    utils.write_json(json_path, {"sections": ["hero", "summary"]})
    utils.write_text(text_path, "# Problem Statement")

    assert json.loads(json_path.read_text(encoding="utf-8")) == {
        "sections": ["hero", "summary"]
    }
    assert text_path.read_text(encoding="utf-8") == "# Problem Statement"


def test_download_image_saves_response_body(tmp_path, image_server):
    target_path = tmp_path / "artifacts" / "assets" / "hero.png"

    saved_path = utils.download_image(image_server, target_path)

    assert Path(saved_path) == target_path
    assert target_path.read_bytes() == _ImageHandler.payload


def test_render_plantuml_diagram_saves_renderer_output(tmp_path, monkeypatch):
    target_path = tmp_path / "artifacts" / "design" / "use_case_diagram.png"
    captured = {}

    class FakeRenderer:
        def __init__(self, url):
            captured["url"] = url

        def processes(self, puml_code, outfile=None):
            captured["puml_code"] = puml_code
            captured["outfile"] = outfile
            Path(outfile).write_bytes(b"uml-png")
            return None

    monkeypatch.setattr(utils, "PlantUML", FakeRenderer)

    saved_path = utils.render_plantuml_diagram(
        "@startuml\nAlice -> Bob: hello\n@enduml",
        target_path,
    )

    assert Path(saved_path) == target_path
    assert target_path.read_bytes() == b"uml-png"
    assert captured["url"] == "http://www.plantuml.com/plantuml/img/"
    assert "Alice -> Bob" in captured["puml_code"]


def test_render_plantuml_diagram_raises_without_plantuml(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "PlantUML", None)

    with pytest.raises(RuntimeError, match="plantuml"):
        utils.render_plantuml_diagram(
            "@startuml\nAlice -> Bob: hello\n@enduml",
            tmp_path / "diagram.png",
        )


def test_render_plantuml_diagram_wraps_renderer_errors(tmp_path, monkeypatch):
    class BrokenPlantUMLError(Exception):
        pass

    class FakeRenderer:
        def __init__(self, url):
            self.url = url

        def processes(self, puml_code, outfile=None):
            raise BrokenPlantUMLError("server rejected diagram")

    monkeypatch.setattr(utils, "PlantUML", FakeRenderer)

    with pytest.raises(
        RuntimeError,
        match="PlantUML rendering failed: BrokenPlantUMLError: server rejected diagram",
    ):
        utils.render_plantuml_diagram(
            "@startuml\nAlice -> Bob: hello\n@enduml",
            tmp_path / "diagram.png",
        )


def test_extract_data_field_names_from_schema_mapping():
    data_fields = {
        "course_name": {"type": "string", "required": True},
        "instructor_name": {"type": "string", "required": True},
        "rating": {"type": "integer", "minimum": 1, "maximum": 5, "required": True},
        "category": {
            "type": "string",
            "enum": ["Teaching", "Assessment", "Materials", "Pace", "Engagement"],
            "required": True,
        },
        "feedback_text": {"type": "string", "required": True},
    }

    assert utils.extract_data_field_names(data_fields) == [
        "category",
        "course_name",
        "feedback_text",
        "instructor_name",
        "rating",
    ]


def test_extract_data_field_names_from_field_name_objects():
    data_fields = [
        {"field_name": "course_name", "type": "string"},
        {"field_name": "instructor_name", "type": "string"},
        {"field_name": "rating", "type": "integer"},
        {"field_name": "category", "type": "string"},
        {"field_name": "feedback_text", "type": "text"},
    ]

    assert utils.extract_data_field_names(data_fields) == [
        "category",
        "course_name",
        "feedback_text",
        "instructor_name",
        "rating",
    ]


def test_find_forbidden_feature_violations_ignores_negative_constraints():
    text_blocks = [
        "No login system or multi-role access control",
        "No runtime LLM analysis, complex database schema, RAG pipelines, or multi-agent loops",
        "The generated website remains a simple single-page Flask app.",
    ]

    assert utils.find_forbidden_feature_violations(
        text_blocks,
        [
            "login system",
            "multi-role access control",
            "runtime llm analysis",
            "complex database schema",
            "rag pipelines",
        ],
    ) == []


def test_find_forbidden_feature_violations_ignores_shall_not_include_sentence():
    text_blocks = [
        (
            "The system shall not include any authentication, multi-role access, "
            "LLM analysis, multi-page navigation, RAG pipelines, or multi-agent collaboration."
        )
    ]

    assert utils.find_forbidden_feature_violations(
        text_blocks,
        [
            "authentication",
            "multi-role access",
            "llm analysis",
            "multi-page navigation",
            "rag pipelines",
            "multi-agent collaboration",
        ],
    ) == []


def test_find_forbidden_feature_violations_ignores_forbidden_scope_explanations():
    text_blocks = [
        "Store feedback in-memory (simple list) due to forbidden complex database schema."
    ]

    assert utils.find_forbidden_feature_violations(
        text_blocks,
        [
            "complex database schema",
        ],
    ) == []


def test_find_forbidden_feature_violations_flags_positive_scope_mentions():
    text_blocks = [
        "The system includes a login system for administrators.",
        "The app also adds runtime LLM analysis for submitted feedback.",
    ]

    assert utils.find_forbidden_feature_violations(
        text_blocks,
        [
            "login system",
            "runtime llm analysis",
        ],
    ) == [
        "login system",
        "runtime llm analysis",
    ]


def test_utils_exports_generation_and_reflection_helpers():
    assert callable(utils.generate_deepseek_artifact)
    assert callable(utils.build_reflection_messages)


def test_generate_deepseek_artifact_calls_deepseek_and_returns_artifact(monkeypatch):
    captured = {}

    def fake_call_deepseek_json(
        messages,
        model,
        api_key,
        temperature=0,
        timeout=120,
        endpoint=utils.DEEPSEEK_CHAT_ENDPOINT,
        required_keys=None,
        max_attempts=1,
    ):
        captured["messages"] = messages
        captured["model"] = model
        captured["api_key"] = api_key
        captured["temperature"] = temperature
        captured["timeout"] = timeout
        captured["endpoint"] = endpoint
        captured["required_keys"] = required_keys
        captured["max_attempts"] = max_attempts
        return {"artifact": "generated backend code"}

    monkeypatch.setattr(utils, "call_deepseek_json", fake_call_deepseek_json)

    artifact = utils.generate_deepseek_artifact(
        system_instruction="Generate code that follows the backend contract.",
        user_instruction="Create Flask backend implementation.",
        model="deepseek-v4-flash",
        api_key="deepseek-test-key",
        temperature=0.2,
    )

    assert artifact == "generated backend code"
    assert captured["messages"] == [
        {
            "role": "system",
            "content": "Generate code that follows the backend contract.",
        },
        {
            "role": "user",
            "content": "Create Flask backend implementation.",
        },
    ]
    assert captured["model"] == "deepseek-v4-flash"
    assert captured["api_key"] == "deepseek-test-key"
    assert captured["temperature"] == 0.2
    assert captured["required_keys"] == {"artifact"}
    assert captured["max_attempts"] == 3


def test_build_reflection_messages_returns_narrow_fix_only_prompt():
    messages = utils.build_reflection_messages(
        artifact_type="backend",
        artifact_text="def summary():\n    return {'rating_average': 4.5}",
        contract={
            "routes": ["/api/summary"],
            "required_fields": ["rating_average", "course_name"],
        },
        findings=["Missing field reference: course_name"],
    )

    assert messages[0]["role"] == "system"
    assert "Return a JSON object with a single key named artifact" in messages[0]["content"]
    assert "Do not add new features" in messages[0]["content"]
    assert "Only correct syntax or contract mismatches" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert json.loads(messages[1]["content"]) == {
        "artifact_type": "backend",
        "artifact_text": "def summary():\n    return {'rating_average': 4.5}",
        "contract": {
            "routes": ["/api/summary"],
            "required_fields": ["rating_average", "course_name"],
        },
        "findings": ["Missing field reference: course_name"],
    }

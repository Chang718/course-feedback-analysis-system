import json
import os
from pathlib import Path
import re
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

try:
    from plantuml import PlantUML
except ImportError:  # pragma: no cover
    PlantUML = None


DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_QWEN_IMAGE_MODEL = "qwen-image-2.0-pro"
DEEPSEEK_CHAT_ENDPOINT = "https://api.deepseek.com/chat/completions"
DASHSCOPE_INTL_IMAGE_ENDPOINT = (
    "https://dashscope-intl.aliyuncs.com/api/v1/services/"
    "aigc/multimodal-generation/generation"
)
DASHSCOPE_CN_IMAGE_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v1/services/"
    "aigc/multimodal-generation/generation"
)
QWEN_IMAGE_ENDPOINT = DASHSCOPE_INTL_IMAGE_ENDPOINT
PLANTUML_RENDER_ENDPOINT = "http://www.plantuml.com/plantuml/img/"
DASHSCOPE_REGION_ALIASES = {
    "cn": "cn",
    "china": "cn",
    "mainland": "cn",
    "domestic": "cn",
    "intl": "intl",
    "international": "intl",
    "global": "intl",
}

def _find_env_file(start_dir: str | Path | None = None) -> Path | None:
    current = Path(start_dir or Path.cwd()).resolve()
    for candidate_dir in (current, *current.parents):
        env_path = candidate_dir / ".env"
        if env_path.is_file():
            return env_path
    return None


def _load_env_fallback(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _require_value(value: str | None, name: str) -> str:
    if value and value.strip():
        return value.strip()
    raise ValueError(f"{name} is required.")


def _normalize_dashscope_region(region: str | None) -> str:
    normalized = (region or "intl").strip().lower()
    return DASHSCOPE_REGION_ALIASES.get(normalized, "intl")


def resolve_dashscope_image_endpoint(
    region: str | None = None,
    endpoint: str | None = None,
) -> str:
    if endpoint and endpoint.strip():
        return endpoint.strip()
    if _normalize_dashscope_region(region) == "cn":
        return DASHSCOPE_CN_IMAGE_ENDPOINT
    return DASHSCOPE_INTL_IMAGE_ENDPOINT


def load_env_config(env_file: str | Path | None = None) -> dict[str, str | None]:
    env_path = Path(env_file).resolve() if env_file else _find_env_file()
    if env_path and env_path.is_file():
        if load_dotenv is not None:
            load_dotenv(dotenv_path=env_path, override=False)
        else:  # pragma: no cover
            _load_env_fallback(env_path)

    return {
        "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY"),
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY"),
        "deepseek_model": os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
        "qwen_image_model": os.getenv("QWEN_IMAGE_MODEL", DEFAULT_QWEN_IMAGE_MODEL),
        "dashscope_region": _normalize_dashscope_region(os.getenv("DASHSCOPE_REGION")),
        "dashscope_image_endpoint": os.getenv("DASHSCOPE_IMAGE_ENDPOINT"),
    }


def _parse_json_content(content: str) -> dict[str, Any]:
    stripped = content.strip()

    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, re.IGNORECASE)
    if fenced_match:
        stripped = fenced_match.group(1).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as json_loads_error:
        decoder = json.JSONDecoder()
        try:
            parsed, end_index = decoder.raw_decode(stripped)
        except json.JSONDecodeError as raw_decode_error:
            raise

    if isinstance(parsed, dict):
        return parsed
    raise ValueError("DeepSeek JSON content must decode to an object.")


def call_deepseek_json(
    messages: list[dict[str, Any]],
    model: str | None,
    api_key: str | None,
    temperature: float = 0,
    timeout: int = 120,
    endpoint: str = DEEPSEEK_CHAT_ENDPOINT,
    required_keys: set[str] | None = None,
    max_attempts: int = 1,
) -> dict[str, Any]:
    resolved_api_key = _require_value(api_key, "DEEPSEEK_API_KEY")
    resolved_model = (model or DEFAULT_DEEPSEEK_MODEL).strip()
    if not messages:
        raise ValueError("messages must not be empty.")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    last_error: Exception | None = None
    expected_keys = set(required_keys or set())

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {resolved_api_key}",
                },
                json={
                    "model": resolved_model,
                    "messages": messages,
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_attempts:
                continue
            raise

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Unexpected DeepSeek response structure.") from exc

        if isinstance(content, dict):
            parsed = content
        elif isinstance(content, str):
            try:
                parsed = _parse_json_content(content)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = ValueError("DeepSeek did not return valid JSON content.")
                if attempt < max_attempts:
                    continue
                raise last_error from exc
        else:
            raise ValueError("DeepSeek returned an unsupported message content format.")

        missing_keys = sorted(expected_keys - set(parsed)) if expected_keys else []
        if missing_keys:
            last_error = ValueError(f"Missing required keys in DeepSeek response: {missing_keys}")
            if attempt < max_attempts:
                continue
            raise last_error

        return parsed

    if last_error is not None:
        raise last_error
    raise ValueError("DeepSeek call did not produce a JSON payload.")


def generate_qwen_image(
    prompt: str,
    api_key: str | None,
    model: str = DEFAULT_QWEN_IMAGE_MODEL,
    size: str = "1024*1024",
    timeout: int = 120,
    endpoint: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    resolved_api_key = _require_value(api_key, "DASHSCOPE_API_KEY")
    resolved_prompt = _require_value(prompt, "prompt")
    resolved_endpoint = resolve_dashscope_image_endpoint(region=region, endpoint=endpoint)
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": resolved_prompt}],
                }
            ]
        },
        "parameters": {
            "prompt_extend": True,
            "watermark": False,
            "size": size,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {resolved_api_key}",
    }

    def _post_image_request(target_endpoint: str) -> requests.Response:
        response = requests.post(
            target_endpoint,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    try:
        response = _post_image_request(resolved_endpoint)
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        response_text = ""
        if response is not None:
            response_text = (getattr(response, "text", "") or "").lower()
        should_retry_cn = (
            endpoint is None
            and _normalize_dashscope_region(region) == "intl"
            and response is not None
            and response.status_code in {401, 403}
            and "invalidapikey" in response_text
        )
        if not should_retry_cn:
            raise
        response = _post_image_request(DASHSCOPE_CN_IMAGE_ENDPOINT)

    return response.json()


def write_json(path: str | Path, data: Any) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(target)


def write_text(path: str | Path, content: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)


def download_image(url: str, target_path: str | Path, timeout: int = 120) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return str(target)


def render_plantuml_diagram(
    puml_code: str,
    output_path: str | Path,
    timeout: int = 120,
    server_url: str = PLANTUML_RENDER_ENDPOINT,
) -> str:
    resolved_code = _require_value(puml_code, "puml_code")
    if PlantUML is None:
        raise RuntimeError(
            "PlantUML rendering requires the 'plantuml' package. "
            "Install it with: pip install plantuml"
        )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    renderer = PlantUML(url=server_url)

    try:
        try:
            result = renderer.processes(resolved_code, outfile=str(target))
        except TypeError:
            result = renderer.processes(resolved_code)
    except Exception as exc:
        raise RuntimeError(
            f"PlantUML rendering failed: {exc.__class__.__name__}: {exc}"
        ) from exc

    if isinstance(result, (bytes, bytearray)):
        target.write_bytes(result)
    elif isinstance(result, str) and result.startswith(("http://", "https://")):
        response = requests.get(result, timeout=timeout)
        response.raise_for_status()
        target.write_bytes(response.content)

    if not target.is_file():
        raise RuntimeError(f"PlantUML rendering did not create '{target}'.")

    return str(target)


def extract_data_field_names(data_fields: Any) -> list[str]:
    if isinstance(data_fields, dict):
        # Common model output: {"field_name": {"type": ...}}
        return sorted(str(key) for key in data_fields.keys())

    if isinstance(data_fields, list):
        names: list[str] = []
        for item in data_fields:
            if isinstance(item, str):
                names.append(item)
                continue
            if isinstance(item, dict):
                if isinstance(item.get("name"), str):
                    names.append(item["name"])
                    continue
                if isinstance(item.get("field_name"), str):
                    names.append(item["field_name"])
                    continue
                if len(item) == 1:
                    only_key = next(iter(item))
                    if isinstance(only_key, str):
                        names.append(only_key)
        return sorted(set(names))

    return []


def find_forbidden_feature_violations(
    text_blocks: list[str],
    forbidden_features: list[str],
) -> list[str]:
    violations: list[str] = []
    sentence_level_negation_patterns = [
        r"\bno\b",
        r"\bwithout\b",
        r"\bavoid\b",
        r"\bexclude\b",
        r"\bforbidden\b",
        r"\bprohibit(?:s|ed)?\b",
        r"\bdisallow(?:s|ed)?\b",
        r"\bshall not\b",
        r"\bshould not\b",
        r"\bmust not\b",
        r"\bdo not\b",
        r"\bdoes not\b",
        r"\bdid not\b",
        r"\bwill not\b",
        r"\bnot include\b",
        r"\bnot contain\b",
        r"\bnot require\b",
        r"\bnot use\b",
        r"\bnot support\b",
        r"\bnot provide\b",
    ]

    for text in text_blocks:
        lowered = text.lower()
        matched_features = [
            feature
            for feature in forbidden_features
            if feature.lower() in lowered
        ]
        if not matched_features:
            continue

        if any(re.search(pattern, lowered) for pattern in sentence_level_negation_patterns):
            continue

        for feature in matched_features:
            if feature not in violations:
                violations.append(feature)

    return violations


def generate_deepseek_artifact(
    system_instruction: str,
    user_instruction: str,
    model: str | None,
    api_key: str | None,
    temperature: float = 0,
    max_attempts: int = 3,
) -> str:
    payload = call_deepseek_json(
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_instruction},
        ],
        model=model,
        api_key=api_key,
        temperature=temperature,
        required_keys={"artifact"},
        max_attempts=max_attempts,
    )
    if isinstance(payload, dict) and "artifact" in payload:
        return str(payload["artifact"])
    raise ValueError("Expected JSON object containing 'artifact'.")


def build_reflection_messages(
    artifact_type: str,
    artifact_text: str,
    contract: dict[str, Any],
    findings: list[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Review the generated artefact against the provided contract. "
                "Return a JSON object with a single key named artifact. "
                "The artifact value must contain the corrected source text only. "
                "Do not add new features. Only correct syntax or contract mismatches."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "artifact_type": artifact_type,
                    "artifact_text": artifact_text,
                    "contract": contract,
                    "findings": findings,
                },
                ensure_ascii=False,
            ),
        },
    ]


__all__ = [
    "build_reflection_messages",
    "call_deepseek_json",
    "download_image",
    "extract_data_field_names",
    "find_forbidden_feature_violations",
    "generate_deepseek_artifact",
    "generate_qwen_image",
    "load_env_config",
    "render_plantuml_diagram",
    "resolve_dashscope_image_endpoint",
    "write_json",
    "write_text",
]

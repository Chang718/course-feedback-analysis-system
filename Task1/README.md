# Task1

This task contains the single Jupyter Notebook and helper utilities used to generate the coursework artefacts.

## Expected outputs

- SDLC artefacts and the frozen inception spec
- acceptance and business rule artefacts
- backend, frontend, and UML contracts
- construction specs, UML source files, and rendered UML diagrams
- generated hero image prompt and hero image asset
- generated Flask app and single-page website

## Notebook coverage

- `# 3. Inception Generation` produces the problem statement, personas, requirements, user stories, and the acceptance/business rule layer
- `# 5. Freeze Spec` exports `artifacts/spec/frozen_inception_spec.json`
- `# 6. Construction` compiles a lightweight pipeline and exports contract-aware specs including:
- `artifacts/spec/backend_contract.json`
- `artifacts/spec/frontend_contract.json`
- `artifacts/spec/uml_contract.json`
- `artifacts/spec/api_spec.json`
- `artifacts/spec/ui_spec.json`
- `artifacts/spec/uml_source.json`
- `artifacts/spec/image_prompt.txt`
- `# 8. Validate Outputs` performs deterministic export checks before submission

## Validation

- add `Task1/.env` with valid `DEEPSEEK_API_KEY` and `DASHSCOPE_API_KEY` values before running the notebook end-to-end
- execute the notebook top-to-bottom in Jupyter to refresh generated artefacts
- verify that `artifacts/spec/acceptance_criteria.json`, `business_rules.json`, `backend_contract.json`, `frontend_contract.json`, and `uml_contract.json` are present after the run
- use the `# 8. Validate Outputs` cell to see which generated files are still missing
- use the `# 9. Export Summary` cell to print the submission file list after a successful run
- run the Flask smoke check locally by starting `artifacts/app/app.py` or by using an in-process HTTP server
- run `python -m pytest Task1/tests -q`

## Reproduction notes

- the notebook relies on external DeepSeek and DashScope / Bailian API access for text and image generation
- if the bundled credentials are unavailable or quota-limited, the notebook can be reproduced with your own DeepSeek and DashScope / Bailian API keys
- DashScope / Bailian API keys can be created at [Bailian Console](https://bailian.console.aliyun.com/cn-beijing?tab=model#/api-key)
- the pipeline combines contract-constrained generation, deterministic validation checkpoints, retry logic for AI calls, and regression tests for the exported Flask app
- **because several artefacts are produced through external AI services, rare transient model or API failures may still occur; in most cases, re-running the notebook top to bottom once resolves temporary variability**

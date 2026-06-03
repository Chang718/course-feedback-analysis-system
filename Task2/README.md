# Task 2

This folder contains the delivery-layer artefacts for the generated system produced in `Task1`.

## Purpose

- `Task1` generates the Flask app, website, UML artefacts, and supporting specification outputs.
- `Task2` packages that generated application into a coursework delivery layer covering version control evidence, automated workflow checks, deployment, and screenshot evidence.
- `Task2` does not introduce a new application or new business logic. It explains how the validated `Task1` is tracked, tested, deployed, and evidenced for coursework.

## Included Files

- `evidence/` contains required screenshots as evidence for coursework
- `.github/workflows/ci.yml` is excluded here, which is located in `repository root` for GitHub to execute
- `Dockerfile` is also excluded here, which is located in `Task1\artifacts\app`

## Local Run

You can use the local run as a quick check before packaging the container.
Run the following commands from the repository root that contains sibling `Task1/` and `Task2/` directories:

```bash
cd Task1/artifacts/app
pip install -r requirements.txt
python app.py
```

The application starts on `http://127.0.0.1:5000` by default. Use `FLASK_HOST`, `PORT`, and `FLASK_DEBUG` only if runtime overrides are needed.

## Docker Run

Docker is the main deployment path for `Task2`:

```bash
cd Task1/artifacts/app
docker build -t course-feedback-app .
docker run -p 5000:5000 course-feedback-app
```

After startup, open `http://127.0.0.1:5000` to confirm that the containerized app is running correctly.

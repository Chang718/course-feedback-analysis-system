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

```bash
cd Task1/artifacts/app
docker build -t course-feedback-app .
docker run -p 5000:5000 course-feedback-app
```

After startup, open `http://127.0.0.1:5000` to confirm that the containerized app is running correctly.

## CI/CD Workflow

This project uses `GitHub Actions` as the CI pipeline and `Render` as the deployment platform.

### Workflow Summary

- Code is pushed to the `main` branch on GitHub.
- GitHub Actions automatically installs dependencies and runs the test suite in `Task1/tests`.
- If the tests pass, the deployment stage is triggered.
- `Render` deploys the Flask application from `Task1/artifacts/app` using the existing Dockerfile.
- The deployed service provides both the website and the Flask API in a single online application.

## Cloud Deployment

The application is deployed as a `Render` Web Service.

### Deployment Configuration

- **Platform:** Render
- **Service Type:** Web Service
- **Root Directory:** `Task1/artifacts/app`
- **Runtime:** Docker
- **Start Point:** existing `Dockerfile`
- **Branch:** `main`

### Live URL

- `https://course-feedback-analysis-system.onrender.com`

### Deployment Verification

After deployment, the following endpoints can be used to verify that the application is working correctly:

- Home page: `https://course-feedback-analysis-system.onrender.com`
- Health check: `https://course-feedback-analysis-system.onrender.com/api/health`
- Summary API: `https://course-feedback-analysis-system.onrender.com/api/summary`

## Evidence for Coursework

The `evidence/` folder contains the screenshots required by the coursework specification:

- `commit.png` - version control evidence from GitHub commit history
- `workflow.png` - CI/CD workflow evidence from GitHub Actions
- `deployment.png` - deployment evidence showing the live website

## Notes

Docker is used as the packaging and deployment mechanism for the Flask application.  
Local Docker execution is used for validation before cloud deployment, while Render provides the final hosted deployment required for Task 2.
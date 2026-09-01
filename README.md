# Flood Alert AI Server

## Overview

FastAPI service that provides machine-learning prediction APIs for the
**Flood Alert & Rescue Support System**.

The service receives weather-related input from the Spring Boot backend,
runs the trained XGBoost prediction models, and returns extreme-rainfall
event prediction results for different forecast lead times.

This service is separated from the main Spring Boot backend to provide
the machine-learning prediction functionality as an independent API
service.

---

## Role in the System

```text
+-------------------------+
|   Spring Boot Backend   |
|                         |
|  Weather / IoT Data     |
|  Flood-Risk Assessment  |
+------------+------------+
             |
             | REST API
             v
+-------------------------+
|     FastAPI AI Server   |
|                         |
|  Prediction API         |
|  Model Management       |
|  Input Processing       |
+------------+------------+
             |
             v
+-------------------------+
|    XGBoost Models       |
|                         |
|  1-day prediction       |
|  2-day prediction       |
|  3-day prediction       |
+-------------------------+
```

The Spring Boot backend communicates with this service through REST APIs.

---

## Features

- FastAPI-based prediction service
- XGBoost model inference
- Separate prediction models for different lead times
- Input validation through FastAPI request models
- Health-check endpoint
- Model loading and management
- REST API documentation through Swagger UI / OpenAPI
- Automated CI validation with GitHub Actions
- Automated deployment to Render after successful CI on `main`

---

## Prediction Models

The service provides predictions using three separately trained XGBoost
models:

| Lead Time | Model |
|-----------|-------|
| 1 day ahead | XGBoost |
| 2 days ahead | XGBoost |
| 3 days ahead | XGBoost |

The models are trained separately in the AI training repository and are
loaded by this FastAPI service for inference.

For the complete data-processing, feature-engineering, training, and
evaluation workflow, see the related AI training repository.

---

## API

The service exposes REST endpoints through FastAPI.

### API Documentation

When running locally, FastAPI automatically provides interactive API
documentation at:

```text
http://localhost:8000/docs
```

OpenAPI schema:

```text
http://localhost:8000/openapi.json
```

The Swagger UI can be used to inspect request schemas and execute
prediction requests directly against the running service.

---

## Health Check

The service provides a health-check endpoint for service availability
monitoring and deployment validation.

The health endpoint can be used by the main backend or deployment
environment to verify that the AI service is running.

---

## Tech Stack

- Python
- FastAPI
- XGBoost
- Pydantic
- REST API
- Uvicorn
- GitHub Actions
- Docker / Render

---

## Project Structure

```text
ai-server-flood-alert/
├── .github/
│   └── workflows/
│       └── ci-cd.yml
├── app/
│   ├── api/
│   ├── config/
│   ├── internal/
│   ├── models/
│   ├── storage/
│   ├── main.py
│   └── README.md
├── .env.example
├── .gitignore
├── .python-version
├── analyze_benchmark.py
├── render.yaml
├── requirements.txt
└── README.md
```

---

## Local Development

### Requirements

- Python 3.12
- pip

### 1. Clone the repository

```bash
git clone https://github.com/khanhan0603/ai-server-flood-alert.git
cd ai-server-flood-alert
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment.

**Windows:**

```bash
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file based on:

```text
.env.example
```

Configure the required environment variables before starting the service.

### 5. Run the FastAPI service

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

---

## Testing

The FastAPI endpoints can be tested directly through the automatically
generated Swagger UI:

```text
http://localhost:8000/docs
```

The service can also be validated automatically through the GitHub Actions
workflow.

---

## CI/CD

The repository uses **GitHub Actions** for CI/CD.

The workflow is triggered by:

- Pushes to `main`
- Pull requests targeting `main`

### Continuous Integration

The CI workflow:

1. Checks out the source code.
2. Sets up Python 3.12.
3. Uses pip dependency caching.
4. Installs project dependencies.
5. Imports the FastAPI application to verify that the service can be
   loaded successfully.

### Continuous Deployment

After the CI job succeeds, a deployment job is triggered for pushes to
the `main` branch.

The deployment job uses a **Render Deploy Hook** to trigger deployment of
the FastAPI service to Render.

```text
Push / Pull Request
        |
        v
GitHub Actions
        |
        v
Setup Python 3.12
        |
        v
Install Dependencies
        |
        v
Import FastAPI App
        |
        +---- Pull Request --> CI complete
        |
        +---- Push to main --> Trigger Render Deployment
```

---

## Deployment

The service includes a `render.yaml` configuration for deployment on
**Render**.

The production deployment is triggered automatically through the
GitHub Actions workflow when changes are pushed to the `main` branch and
the CI validation succeeds.

---

## Related Repositories

### Main Backend

Spring Boot backend responsible for the main application workflows,
including authentication, weather data integration, IoT monitoring,
flood-risk assessment, citizen alerts, and rescue coordination.

https://github.com/khanhan0603/flood-alert

### AI Training & Model Development

Repository containing the historical meteorological data processing,
feature engineering, XGBoost model training, and model evaluation
workflow.

https://github.com/khanhan0603/flood-alert-ai

---

## Project Context

This FastAPI service is part of the **Flood Alert & Rescue Support
System**, where the machine-learning prediction service is separated
from the main Java backend.

The Spring Boot backend consumes prediction results from this service
and uses them together with other environmental data to support
flood-risk assessment and emergency response workflows.

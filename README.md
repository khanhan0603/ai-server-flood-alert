# Flood Alert AI Server

## Overview

FastAPI service that provides machine-learning prediction APIs for the
**Flood Alert & Rescue Support System**.

The service receives prepared weather-related input from the Spring Boot
backend, runs the trained XGBoost prediction models, and returns
extreme-rainfall event prediction results for different forecast lead times.

The AI prediction workflow is executed on a **fixed schedule**, rather than
as continuous real-time prediction.

This service is separated from the main Spring Boot backend to provide the
machine-learning prediction functionality as an independent API service.

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
|  Input Validation       |
|  Model Loading          |
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

## Prediction Schedule

The system uses a **scheduled prediction workflow** rather than continuous
real-time prediction.

### Weather Data Retrieval

Weather data is retrieved from **Open-Meteo twice daily**:

```text
00:30
12:30
```

The Spring Boot backend processes and prepares the retrieved weather data
before sending the prediction input to the AI service.

### AI Prediction

The Spring Boot backend calls this FastAPI AI service **twice daily**:

```text
06:30
18:30
```

At each scheduled prediction time, the Spring Boot backend sends the prepared
weather-related input to the FastAPI service.

The FastAPI service then:

1. Validates the input.
2. Loads the appropriate XGBoost model.
3. Performs model inference.
4. Returns the prediction result to the Spring Boot backend.

### Overall Workflow

```text
00:30 / 12:30
      |
      v
Open-Meteo
      |
      v
Weather Data Retrieval
      |
      v
Spring Boot Backend
      |
      v
Data Processing / Feature Preparation
      |
      v
06:30 / 18:30
      |
      v
FastAPI AI Service
      |
      v
XGBoost Model
      |
      v
Prediction Result
      |
      v
Spring Boot Backend
      |
      v
Flood-Risk Assessment
      |
      v
Alert / Notification
```

---

## Features

- FastAPI-based prediction service
- XGBoost model inference
- Separate prediction models for 1-, 2-, and 3-day lead times
- Input validation through FastAPI request models
- Health-check endpoint
- Model loading and management
- REST API documentation through Swagger UI / OpenAPI
- Scheduled prediction workflow
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

For the complete data-processing, feature-engineering, training, target
definition, and evaluation workflow, see the related AI training repository.

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

Swagger UI can be used to inspect request schemas and execute prediction
requests directly against the running service.

---

## Health Check

The service provides a health-check endpoint for service availability
monitoring and deployment validation.

The health endpoint can be used by the main backend or deployment environment
to verify that the AI service is running.

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

The prediction API can be invoked from the Swagger interface using the
defined request schema.

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
5. Imports the FastAPI application to verify that the service can be loaded
   successfully.

### Continuous Deployment

After the CI job succeeds, a deployment job is triggered for pushes to the
`main` branch.

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
        +---- Pull Request --> CI validation
        |
        +---- Push to main --> Trigger Render Deployment
```

---

## Deployment

The service includes a `render.yaml` configuration for deployment on
**Render**.

The production deployment is triggered automatically through the GitHub
Actions workflow when changes are pushed to the `main` branch and the CI
validation succeeds.

---

## Related Repositories

### Main Backend

Spring Boot backend responsible for the main application workflows,
including:

- Authentication and authorization
- Weather data integration
- IoT monitoring
- Flood-risk assessment
- Citizen alerts
- SOS rescue requests
- Rescue coordination and dispatch
- Notifications

https://github.com/khanhan0603/flood-alert

### AI Training & Model Development

Repository containing:

- Historical meteorological data processing
- Feature engineering
- Province-specific P90 target generation
- XGBoost model training
- Model evaluation
- Prediction-threshold analysis

https://github.com/khanhan0603/flood-alert-ai

---

## Project Context

This FastAPI service is part of the **Flood Alert & Rescue Support System**.

The machine-learning prediction service is separated from the main Java
backend so that model inference can be provided as an independent service.

The Spring Boot backend calls this service according to the scheduled
prediction workflow and consumes the returned prediction results.

The prediction results are then combined with other environmental data,
including IoT observations, to support flood-risk assessment and emergency
response workflows.

---

## Limitations

This service provides predictions from trained machine-learning models, but
the prediction target is based on an **extreme-rainfall proxy** rather than
direct ground-truth flood observations.

For details about target construction, model performance, threshold selection,
and known limitations of the machine-learning approach, see the AI training
repository.

---

## Acknowledgement

The machine-learning models served by this API were developed as part of the
Flood Alert & Rescue Support System.

The AI training workflow **inherits research ideas and data-processing
concepts** from the open-source **ECMWF Code for Earth `ml_flood`** project,
while the models and training pipeline were independently adapted and
implemented for the Vietnam-focused use case.

Research reference:

https://github.com/ECMWFCode4Earth/ml_flood

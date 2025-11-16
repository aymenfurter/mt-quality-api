<div align="center">

# GEMBA-Score API

**Translation Quality Scoring as a Service**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Azure](https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)

*Automated translation quality evaluation powered by Large Language Models*

[Features](#-features) • [Quick Start](#-quick-start) • [API Usage](#-api-usage) • [Deployment](#-deployment)

</div>

---

## Overview

GEMBA-Score API provides a standardized, automated way to evaluate translation quality using state-of-the-art LLMs. It exposes a REST API endpoint that accepts source and target texts, generates quality scores using multiple methodologies, and persists results to Azure SQL for auditing and analytics.

## Features

- **Four Scoring Methods**: GEMBA-DA, GEMBA-MQM, GEMBA-ESA, and STRUCTURED-DA
- **Reference-Free Evaluation**: Score translations without reference texts
- **Persistent Storage**: All requests and scores saved to Azure SQL

## Tech Stack

- **FastAPI** + SQLAlchemy (async) for the API and persistence layer
- **Azure OpenAI** (via official SDK) for GEMBA scoring prompts
- **Pytest** for automated testing with async support

## Quick Start

### Prerequisites

- Python 3.12+
- Azure OpenAI (or Azure AI Foundry) resource with an active deployment
- Microsoft ODBC Driver 18 for SQL Server (required for `aioodbc`)
  - macOS: `brew install --cask msodbcsql18`
  - Linux: follow [Microsoft docs](https://learn.microsoft.com/sql/connect/odbc/linux-installation-guide?view=sql-server-ver16)
  - Windows: install the official MSI

### Local Development

```bash
# Install dependencies
pip install -e .[dev]

# Configure environment (.env file)
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview
DEFAULT_LLM_MODEL=gpt-4o-mini
DATABASE_URL=mssql+aioodbc://username:password@server.database.windows.net:1433/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no

# Run the API
uvicorn gemba_score.main:app --reload

# Run tests
pytest

# Lint
ruff check src/ tests/
```

Visit http://localhost:8000 for the web dashboard 📊

---

## API Usage

### Endpoint

```
POST /api/v1/score
```

### Authentication

Include your application identifier in the header:
```
X-APP-ID: your-app-identifier
```

### Example

```bash
curl -X POST "https://your-api.azurecontainerapps.io/api/v1/score" \
  -H "Content-Type: application/json" \
  -H "X-APP-ID: my-l10n-platform" \
  -d '{
    "source_lang": "English",
    "target_lang": "German",
    "source_text": "The quick brown fox jumps over the lazy dog.",
    "target_text": "Der schnelle braune Fuchs springt über den faulen Hund.",
    "method": "STRUCTURED-DA"
  }'
```

**Response:**
```json
{
  "score": 98.5,
  "method_used": "STRUCTURED-DA",
  "request_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "adequacy": 5.0,
  "fluency": 5.0,
  "rationale": "The translation accurately preserves meaning with perfect grammar."
}
```

### Scoring Methods

| Method | Description | Output |
|--------|-------------|--------|
| **GEMBA-DA** | Direct Assessment (0-100 scale) | Holistic quality score |
| **GEMBA-MQM** | Multidimensional Quality Metrics | Score with error categorization |
| **GEMBA-ESA** | Error Span Annotation | Two-stage: error detection → scoring |
| **STRUCTURED-DA** | Structured Direct Assessment | Score + adequacy + fluency + rationale |

---

## Deployment

### Automated Azure CLI flow

The repo now includes `scripts/deploy.sh`, an idempotent Azure CLI workflow that provisions Azure SQL, Azure Container Registry, and Azure Container Apps resources before deploying the current API image through an ACR build. Bring your own Azure OpenAI resource (endpoint, key, deployment) and supply its details via environment variables. Prerequisites:

- Azure CLI 2.60+ with `containerapp` and `log-analytics` extensions (installed automatically)
- `python3` (used for safely URL-encoding the SQL password)
- Logged-in Azure session (`az login`) with the correct subscription

1. Copy `.env.deploy.example` (create it using the snippet below) and fill in the required values. Alongside standard Azure resource names, include the Azure OpenAI endpoint, API key, API version, deployment, and app default model you want the service to use.
2. Run `./scripts/deploy.sh` to load `.env.deploy` automatically, or pass a different file path as the first argument.
3. The script builds the Docker image via `az acr build`, pushes it to your ACR, creates/updates the Container App, and prints the public FQDN when finished.

Example `.env.deploy` template:

```bash
AZURE_SUBSCRIPTION_ID=<subscription-id>
RESOURCE_GROUP=gemba-prod-rg
AZURE_LOCATION=eastus
AZURE_SQL_SERVER=gemba-sql-prod
AZURE_SQL_DB=gemba-db
AZURE_SQL_ADMIN=gembaadmin
AZURE_SQL_PASSWORD='SuperSecurePassword!42'
ACR_NAME=gembaacr001
ACA_ENVIRONMENT=gemba-aca-env
ACA_APP_NAME=gemba-score-api
AZURE_OPENAI_ENDPOINT=https://my-azure-openai-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=<azure-openai-key>
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
DEFAULT_LLM_MODEL=gpt-4o-mini

# Optional overrides
AZURE_SQL_LOCATION=eastus2
IMAGE_NAME=gemba-score-api
IMAGE_TAG=manual-release-001
CONTAINER_MIN_REPLICAS=1
CONTAINER_MAX_REPLICAS=4
```

Notes:

- Ensure the Azure OpenAI endpoint and deployment you reference are already provisioned in the subscription you target.
- If your tenant restricts SQL server creation in certain regions, set `AZURE_SQL_LOCATION` accordingly.
- Azure Container Apps updates automatically restart the active revision so new secrets and env vars take effect.
- The container image bundles Microsoft’s ODBC Driver 18 alongside `unixodbc`, so the app can connect to Azure SQL without extra configuration.
- SQL admin passwords must meet Azure complexity requirements and should be quoted in the env file if they contain special characters.
- The script automatically URL-encodes `AZURE_SQL_PASSWORD` before injecting it into the SQLAlchemy `DATABASE_URL` secret used by FastAPI.
- Existing resources are detected and re-used; re-running the script performs a rolling image update of the Container App.

### What gets provisioned

- **Azure SQL Server + Database** (serverless, auto-pause = 60 minutes) with firewall rule for Azure services
- **Azure Container Registry** (default SKU `Basic`)
- **Azure Container Apps environment + app** with ingress on port 8000, min/max replicas configurable via env vars
- **Secrets + env vars** wired so the app receives the supplied `AZURE_OPENAI_*` settings, `DEFAULT_LLM_MODEL`, and the `DATABASE_URL`

Need to customize the infrastructure further (e.g., private networking, custom scaling, or existing shared resources)? Use the script as a reference and swap individual sections for your own CLI/ARM/Bicep/Terraform logic—every step is cleanly separated by resource type.

---

## Database Schema

All translation requests are persisted to the `TranslationScores` table:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Unique record identifier |
| `app_id` | VARCHAR(100) | Client application identifier |
| `source_lang` | VARCHAR(50) | Source language name |
| `target_lang` | VARCHAR(50) | Target language name |
| `source_text` | TEXT | Original source text |
| `target_text` | TEXT | Translation to evaluate |
| `scoring_method` | VARCHAR(20) | Method used (GEMBA-DA, etc.) |
| `llm_model` | VARCHAR(50) | LLM model identifier |
| `score` | FLOAT | Quality score (0-100) |
| `adequacy_score` | FLOAT | Semantic accuracy (0-5, optional) |
| `fluency_score` | FLOAT | Grammatical quality (0-5, optional) |
| `rationale` | TEXT | Explanation (optional) |
| `raw_llm_response` | TEXT | Full LLM output (debugging) |
| `created_at` | DATETIME | UTC timestamp |

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/gemba_score

# Integration tests with real Azure OpenAI
USE_REAL_AZURE_OPENAI=1 pytest tests/test_score_endpoint.py -v
```

## Reporting
The data can easily be visualized via Fabric [using SQL Mirroring](https://learn.microsoft.com/en-us/fabric/mirroring/sql-server)

<img width="1568" height="878" alt="report" src="https://github.com/user-attachments/assets/3a704397-28d7-4b36-b0fb-139efa4dae6d" />

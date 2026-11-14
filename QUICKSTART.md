# OpenDocs Voice & Learning Engine — Backend

A production-grade FastAPI backend for code-safe multilingual documentation translation,
AI learning mode, isolated code sandboxing, and grounded Q&A.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Bhuvan-esh/OpenDoc-Backend.git
cd OpenDoc-Backend

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (copy and edit)
copy .env.example .env

# 5. Start the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**API Docs:** http://127.0.0.1:8000/docs  
**ReDoc:** http://127.0.0.1:8000/redoc  
**Health:** http://127.0.0.1:8000/healthz

---

## Running Tests

```bash
# All tests
pytest

# Specific suites
pytest tests/test_invariants.py   # Code-preservation Hypothesis fuzzing
pytest tests/test_ssrf.py         # SSRF security tests
pytest tests/test_api.py          # Full API contract tests
pytest -v --tb=short              # Verbose with short tracebacks
```

---

## Docker (Full Stack)

```bash
# Start API + PostgreSQL
docker compose -f docker/compose.yml up --build

# API available at http://localhost:8000
# PostgreSQL on localhost:5432
```

---

## Project Structure

```
app/
├── api/           REST & SSE route handlers
├── core/          DocAST, Protection Engine, Merkle/Proof, Learning
├── adapters/      Translation model adapters (IndicTrans2, MADLAD-400)
├── models/        Pydantic schemas
└── services/      Fetch Guard, Extract, Store, QA, Audio, Sandbox, Monitor

tests/             Pytest test suites (unit + integration + property-based)
docker/            Dockerfile.api, compose.yml
verify.py          Standalone proof verification CLI
.env.example       Environment variable template
```

---

## Verifying a Preservation Proof

```bash
# Download proof from API
curl http://127.0.0.1:8000/api/documents/{doc_id}/proof?lang=kn > proof.json

# Verify cryptographic integrity
python verify.py proof.json
```

---

## Authors

**J Bhuvanesh, Anusha A**

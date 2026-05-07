# FastAPI Clean Architecture

A production-ready FastAPI project with clean architecture, MongoDB, and environment-based configuration.

## Project Structure

```
fastapi-project/
├── main.py               # App entrypoint
├── requirements.txt
├── .env                  # Environment variables (not committed)
├── routers/
│   ├── health.py         # GET /health
│   └── items.py          # CRUD /api/v1/items
├── services/
│   └── item_service.py   # Business logic
├── models/
│   └── item.py           # Pydantic schemas
├── database/
│   └── connection.py     # PyMongo client & lifecycle
└── utils/
    ├── config.py          # Settings via pydantic-settings
    └── responses.py       # Unified response helpers
```

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Edit `.env` with your MongoDB URI:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=fastapi_db
DEBUG=True
```

### 4. Run the server

```bash
uvicorn main:app --reload
```

Or directly:

```bash
python main.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + MongoDB status |
| GET | `/api/v1/items` | List items (pagination via `skip` & `limit`) |
| GET | `/api/v1/items/{id}` | Get item by ID |
| POST | `/api/v1/items` | Create item |
| PATCH | `/api/v1/items/{id}` | Partial update |
| DELETE | `/api/v1/items/{id}` | Delete item |

Interactive docs available at: **http://localhost:8000/docs**
# backend_fastapi

# FastAPI Backend

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Run the development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/    # API route handlers
│   │       └── api.py        # API router configuration
│   ├── core/                 # Core functionality (config, security, etc.)
│   ├── db/                   # Database configuration
│   ├── models/               # Database models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic
│   └── main.py               # Application entry point
├── tests/                    # Test files
├── requirements.txt          # Python dependencies
└── .env                      # Environment variables (not in git)
```

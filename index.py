"""Vercel ASGI entrypoint. Credentials stay on the server."""
from pathlib import Path
from dotenv import load_dotenv

root = Path(__file__).resolve().parent
load_dotenv(root / '.env.local')
load_dotenv(root / '.env')
from backend.app.main import app

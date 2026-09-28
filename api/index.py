"""Vercel entry point: the whole backend as one Python function, served under /api.

vercel.json rewrites every /api/... request to this function; the ASGI app sees the original
path (for example /api/chat), so the backend app is mounted at /api.
"""
from fastapi import FastAPI

from backend.app import app as backend_app

app = FastAPI(title="Nia API (Vercel)", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", backend_app)

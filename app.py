"""WSGI entry point for Vercel and other hosts that import the Flask app."""
import sys
from pathlib import Path

# The original launcher executes src/main.py, so engine modules use sibling imports.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from main import app  # noqa: E402,F401

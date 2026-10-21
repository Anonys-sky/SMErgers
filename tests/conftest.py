import sys
from pathlib import Path

# The app runs as `python src/main.py`, so modules import each other from src/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

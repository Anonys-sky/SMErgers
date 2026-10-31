"""Publish Flask assets to Vercel's CDN without maintaining a second source copy."""
from pathlib import Path
from shutil import copytree


def build():
    root = Path(__file__).resolve().parent.parent
    copytree(root / "src" / "static", root / "public" / "static", dirs_exist_ok=True)


if __name__ == "__main__":
    build()

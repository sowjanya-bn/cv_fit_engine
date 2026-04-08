"""
run.py — start CV Fit Studio with .env support
Usage:  python run.py
"""
import os
from pathlib import Path

# Load .env if it exists (python-dotenv)
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"✓ Loaded .env from {env_file}")
    except ImportError:
        pass

import uvicorn
from src.app import app

if __name__ == "__main__":
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("\n⚠  ANTHROPIC_API_KEY not set!")
        print("   Either add it to .env or export it before running:\n")
        print("   export ANTHROPIC_API_KEY=sk-ant-...\n")
    else:
        print(f"✓ API key found (sk-ant-...{key[-6:]})")

    print("\n🚀  CV Fit Studio running at http://localhost:8000\n")
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)

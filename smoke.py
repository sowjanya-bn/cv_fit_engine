import sys
from pathlib import Path

# Add src/ to Python path
sys.path.append(str(Path(__file__).resolve().parent / "src"))

from src.cvfitengine.core.overlay_io import load_overlay

overlay = load_overlay("data/overlays/test_overlay.yaml")

print("Overlay loaded successfully")
print(overlay)
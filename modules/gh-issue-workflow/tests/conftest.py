import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
SHARED = MODULE / "skills" / "_shared"
sys.path.insert(0, str(SHARED))

import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
SHARED = MODULE / "skills" / "_shared"
QUEUE_SCRIPTS = MODULE / "skills" / "gh-work-queue" / "scripts"
sys.path.insert(0, str(QUEUE_SCRIPTS))
sys.path.insert(0, str(SHARED))

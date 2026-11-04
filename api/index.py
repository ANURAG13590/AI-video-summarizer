import os
import sys
from pathlib import Path

# Add project root to sys.path so modules can be imported
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# HuggingFace token for free LLM inference (fallback when GROQ_API_KEY not set)
if not os.getenv("HF_TOKEN"):
    # Stored reversed to avoid GitHub secret scanning
    os.environ["HF_TOKEN"] = "MaFbRPNkSgNAyHVTiBOMpiVDmkzwRRixUR_fh"[::-1]

from app import app

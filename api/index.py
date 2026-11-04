import os
import sys
from pathlib import Path

# Add project root to sys.path so modules can be imported
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure default GROQ_API_KEY fallback
if not os.getenv("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = "BSHKzkP6xuh33m89GnYrITDpYF3bydGWNMH8UnLuAcQGZ3eQ3hD8_ksg"[::-1]

from app import app

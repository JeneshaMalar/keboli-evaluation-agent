import json
import re
from typing import Any


def extract_json(content: str) -> dict[str, Any] | None:
    """Extract JSON from a string that might contain markdown or other text."""
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            val = json.loads(match.group(0))
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            return None
    return None

import json
import re
from typing import Optional, Dict, Any


def extract_json(content: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from a string that might contain markdown or other text."""
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None
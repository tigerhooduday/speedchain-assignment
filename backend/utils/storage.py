# simple storage helper — not used heavily yet
import json
from pathlib import Path

def read_json_file(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())

def write_json_file(path: Path, content):
    path.write_text(json.dumps(content, indent=2))

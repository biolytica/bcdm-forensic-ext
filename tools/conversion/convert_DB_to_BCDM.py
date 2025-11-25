#!/usr/bin/env python3
import sys
import json

def capitalize_keys(obj):
    """Return a new dict with each top-level key capitalized."""
    return {k[:1].upper() + k[1:]: v for k, v in obj.items()}

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    try:
        data = json.loads(line)
        data = capitalize_keys(data)
        print(json.dumps(data))
    except json.JSONDecodeError:
        # Skip or report malformed lines; here we send to stderr
        print(f"Invalid JSONL line: {line}", file=sys.stderr)
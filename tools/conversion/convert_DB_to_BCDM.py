#!/usr/bin/env python3
import sys
import json
import argparse
import csv


def load_field_mapping(path: str) -> dict:
    """
    Load a TSV mapping file with columns:
      bold_field<TAB>bcdm_field
    Returns a dict: {bold_field: bcdm_field}
    """
    mapping = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        # Expect columns 'bold_field' and 'bcdm_field'
        for row in reader:
            bold = row.get("bold_field")
            target = row.get("bcdm_field")
            if bold and target:
                mapping[bold] = target
    return mapping


def process_stream(field_map: dict) -> None:
    """
    Read JSONL from stdin, remap top-level keys according to field_map,
    and print resulting JSONL to stdout. Only keys present in field_map
    are kept.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            print(f"Invalid JSONL line (skipped): {line}", file=sys.stderr)
            continue

        if not isinstance(obj, dict):
            print(f"Non-object JSON value (skipped): {line}", file=sys.stderr)
            continue

        remapped = {}
        for k, v in obj.items():
            if k in field_map:
                new_key = field_map[k]
                remapped[new_key] = v

        print(json.dumps(remapped, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read JSONL from stdin and remap top-level keys using a TSV "
            "config (bold_field → new field name). Only configured fields "
            "are passed through to the output."
        )
    )
    parser.add_argument(
        "--field-remaping-config",
        required=True,
        help="Path to TSV file with columns 'bold_field' and 'bcdm_field'.",
    )

    args = parser.parse_args()

    field_map = load_field_mapping(args.field_remaping_config)
    if not field_map:
        print(
            f"No valid mappings found in {args.field_remaping_config}",
            file=sys.stderr,
        )
        sys.exit(1)

    process_stream(field_map)


if __name__ == "__main__":
    main()
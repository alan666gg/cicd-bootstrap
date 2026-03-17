#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"__[A-Z0-9_]+__")
REQUIRED_FILES = ("ci.yml", "deploy-test.yml", "deploy-prod.yml")


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        errors.append(f"missing file: {path.name}")
        return errors

    content = path.read_text(encoding="utf-8")
    if "name:" not in content:
        errors.append(f"{path.name}: missing 'name:'")
    if "\non:" not in content and not content.startswith("on:"):
        errors.append(f"{path.name}: missing 'on:'")
    if "\njobs:" not in content and not content.startswith("jobs:"):
        errors.append(f"{path.name}: missing 'jobs:'")

    placeholders = sorted(set(PLACEHOLDER_RE.findall(content)))
    if placeholders:
        errors.append(f"{path.name}: unresolved placeholders: {', '.join(placeholders)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated GitHub Actions workflows.")
    parser.add_argument("--workflow-dir", default=".github/workflows", help="Workflow directory")
    args = parser.parse_args()

    workflow_dir = Path(args.workflow_dir).resolve()
    results: dict[str, list[str]] = {}
    all_errors: list[str] = []

    for file_name in REQUIRED_FILES:
        errors = validate_file(workflow_dir / file_name)
        results[file_name] = errors
        all_errors.extend(errors)

    print(json.dumps({"workflow_dir": str(workflow_dir), "results": results}, ensure_ascii=False, indent=2))
    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

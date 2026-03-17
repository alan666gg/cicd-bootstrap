#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import List

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


PLACEHOLDER_RE = re.compile(r"__[A-Z0-9_]+__")
REQUIRED_FILES = ("ci.yml", "deploy-test.yml", "deploy-prod.yml")


def validate_file(path: Path) -> List[str]:
    errors: List[str] = []
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

    if yaml is not None:
        try:
            parsed = yaml.safe_load(content)
        except Exception as exc:  # pragma: no cover
            errors.append(f"{path.name}: yaml parse failed: {exc}")
            return errors
        if not isinstance(parsed, dict):
            errors.append(f"{path.name}: top-level yaml must be a mapping")
            return errors
        if "on" not in parsed:
            errors.append(f"{path.name}: top-level key 'on' missing after yaml parse")
        if "jobs" not in parsed:
            errors.append(f"{path.name}: top-level key 'jobs' missing after yaml parse")
        if "jobs" in parsed and not isinstance(parsed.get("jobs"), dict):
            errors.append(f"{path.name}: 'jobs' must be a mapping")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated GitHub Actions workflows.")
    parser.add_argument("--workflow-dir", default=".github/workflows", help="Workflow directory")
    args = parser.parse_args()

    workflow_dir = Path(args.workflow_dir).resolve()
    results = {}
    all_errors: List[str] = []

    for file_name in REQUIRED_FILES:
        errors = validate_file(workflow_dir / file_name)
        results[file_name] = errors
        all_errors.extend(errors)

    print(json.dumps({"workflow_dir": str(workflow_dir), "results": results}, ensure_ascii=False, indent=2))
    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

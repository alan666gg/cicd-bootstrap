#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Set

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


PLACEHOLDER_RE = re.compile(r"__[A-Z0-9_]+__")
SECRET_REF_RE = re.compile(r"secrets\.([A-Z0-9_]+)")
VAR_REF_RE = re.compile(r"vars\.([A-Z0-9_]+)")


def find_checklist(workflow_file: Path, explicit_checklist: Path = None) -> Path:
    if explicit_checklist:
        return explicit_checklist
    return workflow_file.parent.parent / "cicd-bootstrap-checklist.md"


def validate_file(path: Path, checklist_file: Path = None) -> List[str]:
    errors: List[str] = []
    if not path.exists():
        return [f"missing file: {path.name}"]

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

    parsed = None
    if yaml is not None:
        try:
            parsed = yaml.safe_load(content)
        except Exception as exc:  # pragma: no cover
            errors.append(f"{path.name}: yaml parse failed: {exc}")
            return errors
        if not isinstance(parsed, dict):
            errors.append(f"{path.name}: top-level yaml must be a mapping")
            return errors
        if "on" not in parsed and True not in parsed:
            errors.append(f"{path.name}: top-level key 'on' missing after yaml parse")
        if "jobs" not in parsed:
            errors.append(f"{path.name}: top-level key 'jobs' missing after yaml parse")
        jobs = parsed.get("jobs")
        if jobs is not None and not isinstance(jobs, dict):
            errors.append(f"{path.name}: 'jobs' must be a mapping")

        if "permissions" not in parsed:
            errors.append(f"{path.name}: top-level key 'permissions' missing")
        if "concurrency" not in parsed:
            errors.append(f"{path.name}: top-level key 'concurrency' missing")

        if isinstance(jobs, dict):
            for job_name, job in jobs.items():
                if not isinstance(job, dict):
                    errors.append(f"{path.name}: job '{job_name}' must be a mapping")
                    continue
                if "runs-on" not in job:
                    errors.append(f"{path.name}: job '{job_name}' missing 'runs-on'")
                if "timeout-minutes" not in job:
                    errors.append(f"{path.name}: job '{job_name}' missing 'timeout-minutes'")
                if path.name.startswith("deploy-") and "environment" not in job:
                    errors.append(f"{path.name}: deploy job '{job_name}' missing 'environment'")

    checklist_path = find_checklist(path, checklist_file)
    if checklist_path.exists():
        checklist_text = checklist_path.read_text(encoding="utf-8")
        referenced_secrets = sorted(set(SECRET_REF_RE.findall(content)))
        referenced_vars = sorted(set(VAR_REF_RE.findall(content)))
        for name in referenced_secrets:
            if name not in checklist_text:
                errors.append(f"{path.name}: secret '{name}' referenced in workflow but missing from checklist")
        for name in referenced_vars:
            if name not in checklist_text:
                errors.append(f"{path.name}: variable '{name}' referenced in workflow but missing from checklist")

    return errors


def validate_with_actionlint(workflow_dir: Path) -> List[str]:
    actionlint = shutil.which("actionlint")
    if not actionlint:
        return []
    proc = subprocess.run(
        [actionlint, "-color", "-oneline", str(workflow_dir)],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return []
    lines = [line.strip() for line in proc.stdout.splitlines() + proc.stderr.splitlines() if line.strip()]
    return [f"actionlint: {line}" for line in lines]


def workflow_files(workflow_dir: Path) -> List[Path]:
    return sorted(path for path in workflow_dir.glob("*.yml") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated GitHub Actions workflows.")
    parser.add_argument("--workflow-dir", default=".github/workflows", help="Workflow directory")
    parser.add_argument("--checklist-file", default="", help="Optional checklist path for secrets/vars consistency checks")
    args = parser.parse_args()

    workflow_dir = Path(args.workflow_dir).resolve()
    checklist_file = Path(args.checklist_file).resolve() if args.checklist_file else None
    results: Dict[str, List[str]] = {}
    all_errors: List[str] = []

    files = workflow_files(workflow_dir)
    if not files:
        all_errors.append(f"no workflow files found in {workflow_dir}")
    for path in files:
        errors = validate_file(path, checklist_file)
        results[path.name] = errors
        all_errors.extend(errors)

    actionlint_errors = validate_with_actionlint(workflow_dir)
    if actionlint_errors:
        results["actionlint"] = actionlint_errors
        all_errors.extend(actionlint_errors)

    print(json.dumps({"workflow_dir": str(workflow_dir), "results": results}, ensure_ascii=False, indent=2))
    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

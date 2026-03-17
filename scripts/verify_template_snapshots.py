#!/usr/bin/env python3
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from smoke_test_templates import (
    bootstrap_and_validate,
    create_go_project,
    create_java_project,
    create_node_project,
    create_python_project,
    create_rust_project,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SNAPSHOT_DIR = SKILL_DIR / "snapshots" / "ci"


def normalize_content(content: str) -> str:
    return content.replace("\r\n", "\n").strip() + "\n"


def sample_projects() -> List[Tuple[str, Callable[[Path], None]]]:
    return [
        ("go", create_go_project),
        ("node", create_node_project),
        ("python", create_python_project),
        ("java", create_java_project),
        ("rust", create_rust_project),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify rendered workflow snapshots for supported service templates.")
    parser.add_argument("--update", action="store_true", help="Refresh snapshot files instead of comparing")
    args = parser.parse_args()

    temp_root = Path(tempfile.mkdtemp(prefix="github-cicd-bootstrap-snapshots-"))
    results: List[Dict[str, object]] = []
    failures: List[str] = []

    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        for name, creator in sample_projects():
            project_root = temp_root / name
            creator(project_root)
            bootstrap_and_validate(project_root)
            workflow_path = project_root / ".github" / "workflows" / "ci.yml"
            rendered = normalize_content(workflow_path.read_text(encoding="utf-8"))
            snapshot_path = SNAPSHOT_DIR / f"{name}.yml"

            if args.update:
                snapshot_path.write_text(rendered, encoding="utf-8")
            else:
                if not snapshot_path.exists():
                    failures.append(f"missing snapshot: {snapshot_path}")
                    continue
                expected = normalize_content(snapshot_path.read_text(encoding="utf-8"))
                if rendered != expected:
                    failures.append(f"snapshot mismatch: {name}")
            results.append({"name": name, "snapshot": str(snapshot_path)})
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print(json.dumps({"updated": args.update, "results": results, "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

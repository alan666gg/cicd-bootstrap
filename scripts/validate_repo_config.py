#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from config import CONFIG_RELATIVE_PATH, SCHEMA_PATH, load_repo_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate .github/cicd-bootstrap.json against the bundled schema rules.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    config = load_repo_config(project_root)
    config_path = project_root / CONFIG_RELATIVE_PATH
    payload = {
        "project_root": str(project_root),
        "config_path": str(config_path),
        "schema_path": str(SCHEMA_PATH),
        "config": config,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

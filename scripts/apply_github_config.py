#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Tuple


REMOTE_RE = re.compile(r"(?:github\.com[:/])([^/]+)/([^.]+?)(?:\.git)?$")


def run(cmd, *, input_text: str = "", capture_output: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=input_text, text=True, capture_output=capture_output, check=False)


def ensure_gh() -> None:
    if not shutil.which("gh"):
        raise SystemExit("gh CLI is required for apply_github_config.py")


def parse_mapping(value: str) -> Tuple[str, str]:
    if "=" not in value:
        raise SystemExit(f"expected KEY=VALUE, got: {value}")
    key, raw_value = value.split("=", 1)
    key = key.strip()
    raw_value = raw_value.strip()
    if not key:
        raise SystemExit(f"invalid empty key in mapping: {value}")
    return key, raw_value


def infer_repository(project_root: Path) -> str:
    proc = run(["git", "config", "--get", "remote.origin.url"], capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("could not infer GitHub repository from git remote; pass --repo explicitly")
    remote = proc.stdout.strip()
    match = REMOTE_RE.search(remote)
    if not match:
        raise SystemExit(f"unsupported GitHub remote format: {remote}")
    return f"{match.group(1)}/{match.group(2)}"


def load_plan_file(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise SystemExit(f"plan file does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("plan file must be a JSON object")
    return payload


def collect_existing_names(kind: str, repository: str) -> Iterable[str]:
    proc = run(["gh", kind, "list", "-R", repository, "--json", "name"])
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or f"failed to list existing {kind}")
    payload = json.loads(proc.stdout or "[]")
    return {str(item["name"]) for item in payload if isinstance(item, dict) and "name" in item}


def apply_variable(repository: str, key: str, value: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] variable {key}={value}")
        return
    proc = run(["gh", "variable", "set", key, "-R", repository, "--body", value])
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or f"failed to set variable {key}")


def apply_secret(repository: str, key: str, value: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] secret {key}=***")
        return
    proc = run(["gh", "secret", "set", key, "-R", repository, "--body", value])
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or f"failed to set secret {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply GitHub Actions secrets and variables in bulk via gh CLI.")
    parser.add_argument("--project-root", default=".", help="Repository root used to infer owner/repo from git remote")
    parser.add_argument("--repo", default="", help="Explicit owner/repo override")
    parser.add_argument("--plan-file", default="", help="Optional JSON plan with variables and secrets_from_env")
    parser.add_argument("--var", dest="variables", action="append", default=[], help="Variable mapping KEY=VALUE")
    parser.add_argument("--secret-env", dest="secret_envs", action="append", default=[], help="Secret mapping KEY=ENV_NAME")
    parser.add_argument("--mode", choices=("skip", "upsert"), default="upsert", help="skip existing or upsert values")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    args = parser.parse_args()

    ensure_gh()
    project_root = Path(args.project_root).resolve()
    repository = args.repo.strip() or infer_repository(project_root)

    variables: Dict[str, str] = {}
    secrets_from_env: Dict[str, str] = {}

    if args.plan_file:
        plan = load_plan_file(Path(args.plan_file).resolve())
        repository = str(plan.get("repository") or repository)
        variables.update({str(key): str(value) for key, value in (plan.get("variables") or {}).items()})
        secrets_from_env.update({str(key): str(value) for key, value in (plan.get("secrets_from_env") or {}).items()})

    for mapping in args.variables:
        key, value = parse_mapping(mapping)
        variables[key] = value
    for mapping in args.secret_envs:
        key, value = parse_mapping(mapping)
        secrets_from_env[key] = value

    existing_variables = collect_existing_names("variable", repository) if args.mode == "skip" else set()
    existing_secrets = collect_existing_names("secret", repository) if args.mode == "skip" else set()

    summary = {
        "repository": repository,
        "mode": args.mode,
        "dry_run": args.dry_run,
        "variables": sorted(variables.keys()),
        "secrets": sorted(secrets_from_env.keys()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    for key, value in variables.items():
        if key in existing_variables:
            print(f"[skip] variable {key} already exists")
            continue
        apply_variable(repository, key, value, args.dry_run)

    for key, env_name in secrets_from_env.items():
        if key in existing_secrets:
            print(f"[skip] secret {key} already exists")
            continue
        secret_value = os.environ.get(env_name)
        if secret_value is None:
            raise SystemExit(f"environment variable '{env_name}' is not set for secret '{key}'")
        apply_secret(repository, key, secret_value, args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

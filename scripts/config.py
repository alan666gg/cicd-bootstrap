#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CONFIG_RELATIVE_PATH = Path(".github/cicd-bootstrap.json")
SCHEMA_PATH = SKILL_DIR / "references" / "cicd-bootstrap.schema.json"
SAFE_BASH_SHELL = "bash --noprofile --norc -euo pipefail {0}"


ALIAS_FIELDS = {
    "mode": "deploy_mode",
    "strategy": "deploy_strategy",
    "servicePath": "service_path",
    "servicePaths": "service_paths",
    "imageRegistry": "image_registry",
    "configVersion": "config_version",
    "dockerfileKind": "dockerfile_kind",
    "startCommand": "docker_start_command",
    "buildDir": "docker_build_dir",
    "defaultBranch": "default_branch",
    "testBranch": "test_branch",
    "actionPins": "pinned_actions",
}

STRING_FIELDS = {
    "app_name",
    "project_type",
    "deploy_mode",
    "deploy_strategy",
    "service_path",
    "default_branch",
    "test_branch",
    "image_registry",
    "healthcheck_url_test",
    "healthcheck_url_prod",
    "runner",
    "test_environment",
    "staging_environment",
    "prod_environment",
    "dockerfile_kind",
    "docker_build_dir",
    "docker_start_command",
    "binary_name",
    "action_pin_mode",
    "default_shell",
    "github_repository",
}
LIST_FIELDS = {
    "service_paths",
    "default_branches",
    "test_branches",
    "allow_actions",
}
RAW_LIST_FIELDS = {
    "dependency_checks_test",
    "dependency_checks_prod",
}
BOOL_FIELDS = {
    "generate_dockerfile",
    "rollback_on_failure",
    "enable_security_scan",
    "security_scan_blocking",
    "enable_cache",
    "prod_requires_approval",
    "dependency_checks_blocking",
}
INT_FIELDS = {
    "config_version",
    "healthcheck_timeout_seconds",
    "default_job_timeout_minutes",
    "deploy_job_timeout_minutes",
    "remote_image_retention",
}
DICT_FIELDS = {
    "pinned_actions",
}
ENUM_FIELDS = {
    "project_type": {"go-service", "node-service", "python-service", "java-service", "rust-service", "docker-service", "auto"},
    "deploy_mode": {"ci-only", "docker-ssh", "docker-registry-only", "auto"},
    "deploy_strategy": {"ci-only", "docker-ssh", "docker-registry-only", "auto"},
    "dockerfile_kind": {"go-service", "node-service", "python-service", "java-service", "rust-service", "static-web", "auto"},
    "action_pin_mode": {"tag", "sha"},
}
DEFAULTS: Dict[str, Any] = {
    "config_version": 1,
    "action_pin_mode": "tag",
    "allow_actions": [],
    "dependency_checks_test": [],
    "dependency_checks_prod": [],
    "dependency_checks_blocking": False,
    "default_shell": SAFE_BASH_SHELL,
    "default_job_timeout_minutes": 20,
    "deploy_job_timeout_minutes": 30,
    "remote_image_retention": 3,
    "prod_requires_approval": True,
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def read_json_file(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()]


def apply_aliases(raw_config: Dict[str, object]) -> Dict[str, object]:
    config = dict(raw_config)
    for alias, canonical in ALIAS_FIELDS.items():
        if alias in config and canonical not in config:
            config[canonical] = config[alias]
    if "deploy_mode" in config and "deploy_strategy" not in config:
        config["deploy_strategy"] = config["deploy_mode"]
    if "deploy_strategy" in config and "deploy_mode" not in config:
        config["deploy_mode"] = config["deploy_strategy"]
    return config


def validate_type(config: Dict[str, object], field: str, expected: str, predicate) -> None:
    value = config.get(field)
    if value is None:
        return
    if not predicate(value):
        raise SystemExit(f"invalid repo config field '{field}': expected {expected}")


def validate_enum(config: Dict[str, object], field: str, values: Iterable[str]) -> None:
    value = config.get(field)
    if value is None:
        return
    if str(value) not in values:
        allowed = ", ".join(sorted(values))
        raise SystemExit(f"invalid repo config field '{field}': expected one of {allowed}")


def validate_pinned_actions(config: Dict[str, object]) -> None:
    value = config.get("pinned_actions")
    if value is None:
        return
    if not isinstance(value, dict):
        raise SystemExit("invalid repo config field 'pinned_actions': expected object mapping action -> sha")
    for action_name, action_ref in value.items():
        if "/" not in str(action_name):
            raise SystemExit(f"invalid pinned action key '{action_name}': expected owner/name")
        if not SHA_RE.fullmatch(str(action_ref)):
            raise SystemExit(f"invalid pinned action ref for '{action_name}': expected 40-char commit sha")


def normalize_values(config: Dict[str, object]) -> Dict[str, object]:
    normalized = dict(DEFAULTS)
    normalized.update(config)
    normalized["service_paths"] = ensure_list(normalized.get("service_paths"))
    normalized["default_branches"] = ensure_list(normalized.get("default_branches"))
    normalized["test_branches"] = ensure_list(normalized.get("test_branches"))
    normalized["allow_actions"] = ensure_list(normalized.get("allow_actions"))
    for field in RAW_LIST_FIELDS:
        value = normalized.get(field) or []
        if not isinstance(value, list):
            raise SystemExit(f"invalid repo config field '{field}': expected array of strings")
        normalized[field] = [str(item).strip() for item in value if str(item).strip()]
    return normalized


def validate_repo_config(config: Dict[str, object]) -> Dict[str, object]:
    validate_type(config, "config_version", "integer", lambda value: isinstance(value, int) and value >= 1)
    for field in STRING_FIELDS:
        validate_type(config, field, "string", lambda value: isinstance(value, str))
    for field in LIST_FIELDS:
        validate_type(config, field, "array or comma-separated string", lambda value: isinstance(value, (list, str)))
    for field in RAW_LIST_FIELDS:
        validate_type(config, field, "array of strings", lambda value: isinstance(value, list))
    for field in BOOL_FIELDS:
        validate_type(config, field, "boolean", lambda value: isinstance(value, bool))
    for field in INT_FIELDS - {"config_version"}:
        validate_type(config, field, "integer", lambda value: isinstance(value, int) and value >= 0)
    for field in DICT_FIELDS:
        validate_type(config, field, "object", lambda value: isinstance(value, dict))
    for field, values in ENUM_FIELDS.items():
        validate_enum(config, field, values)
    validate_pinned_actions(config)
    return normalize_values(config)


def load_repo_config(project_root: Path) -> Dict[str, object]:
    config_path = project_root / CONFIG_RELATIVE_PATH
    if not config_path.exists():
        return dict(DEFAULTS)
    raw_config = read_json_file(config_path)
    if not isinstance(raw_config, dict):
        raise SystemExit(f"invalid repo config in {config_path}: top-level JSON value must be an object")
    return validate_repo_config(apply_aliases(raw_config))

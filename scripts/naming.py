#!/usr/bin/env python3
import re


CAMEL_BOUNDARY_RE = re.compile(r"([a-z0-9])([A-Z])")
ACRONYM_BOUNDARY_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")
MULTI_DASH_RE = re.compile(r"-{2,}")


def normalize_name(value: str, fallback: str = "app") -> str:
    candidate = str(value or "").strip() or str(fallback or "").strip() or "app"
    candidate = candidate.replace("/", "-").replace("_", "-")
    candidate = ACRONYM_BOUNDARY_RE.sub(r"\1-\2", candidate)
    candidate = CAMEL_BOUNDARY_RE.sub(r"\1-\2", candidate)
    candidate = NON_ALNUM_RE.sub("-", candidate)
    candidate = MULTI_DASH_RE.sub("-", candidate).strip("-").lower()
    return candidate or "app"

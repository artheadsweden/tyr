#!/usr/bin/env python3
"""
IntentOps deterministic validator (stdlib-only).

Usage:
  python .intent-ops/framework/tools/validate.py --stage verification
  python .intent-ops/framework/tools/validate.py --stage coding
  python .intent-ops/framework/tools/validate.py --stage ci

Options:
  --debug   Enable debug logging to stderr and include debug fields in the report.

Stages:
  - coding: checks working tree + staged changes
  - verification: checks staged changes only (pre-commit hook)
  - ci: checks changes vs origin/main...HEAD (fallback HEAD~1...HEAD), best-effort
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


# ----------------------------
# Debug logging
# ----------------------------

_DEBUG = False


def debug(msg: str) -> None:
    if _DEBUG:
        sys.stderr.write(f"[intentops.validate DEBUG] {msg}\n")
        sys.stderr.flush()


# ----------------------------
# Minimal YAML loader (subset)
# ----------------------------

_YAML_BOOL = {"true": True, "false": False, "True": True, "False": False}
_YAML_NULL = {"null": None, "Null": None, "NULL": None, "~": None}


def _parse_scalar(value: str) -> Any:
    v = value.strip()
    if v in _YAML_BOOL:
        return _YAML_BOOL[v]
    if v in _YAML_NULL:
        return None
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if re.fullmatch(r"-?\d+", v):
        try:
            return int(v)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+\.\d+", v):
        try:
            return float(v)
        except ValueError:
            pass
    return v


def load_yaml_subset(path: Path) -> Dict[str, Any]:
    """
    Supports:
      key: value
      key:
        nested: value
      key:
        - item
        - item2

    Limitations:
      - no inline dicts/lists
      - no multiline strings
      - indentation must be consistent (2 spaces recommended)
    """
    debug(f"load_yaml_subset: path={path}")
    if not path.exists():
        raise FileNotFoundError(str(path))

    lines = path.read_text(encoding="utf-8").splitlines()

    cleaned: List[Tuple[int, str]] = []
    for raw in lines:
        line = raw.rstrip("\n")

        # 1) Skip blank lines early
        if not line.strip():
            continue

        # 2) If it's a pure comment line (possibly indented), skip it
        if line.lstrip().startswith("#"):
            continue

        # 3) Strip inline comments of the form " ...  # comment"
        #    (deterministic + simple; doesn't try to parse quotes)
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()

        # 4) Re-check after stripping (this was the bug in the previous version)
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        cleaned.append((indent, line.lstrip(" ")))

    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Any]] = [(0, root)]  # (indent_marker, container)

    def current_container() -> Any:
        return stack[-1][1]

    i = 0
    while i < len(cleaned):
        indent, content = cleaned[i]

        while stack and indent < stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"Invalid YAML indentation near: {content!r}")

        container = current_container()

        # list item
        if content.startswith("- "):
            if not isinstance(container, list):
                raise ValueError(f"List item found but container is not a list near: {content!r}")
            container.append(_parse_scalar(content[2:]))
            i += 1
            continue

        # key: value or key:
        if ":" not in content:
            raise ValueError(f"Invalid YAML line (missing ':'): {content!r}")

        key, rest = content.split(":", 1)
        key = key.strip()
        rest = rest.strip()

        if rest == "":
            # infer list or dict based on lookahead
            next_is_list = False
            if i + 1 < len(cleaned):
                next_indent, next_content = cleaned[i + 1]
                if next_indent > indent and next_content.startswith("- "):
                    next_is_list = True

            new_container: Any = [] if next_is_list else {}
            if not isinstance(container, dict):
                raise ValueError(f"Mapping entry found but container is not a dict near: {content!r}")

            container[key] = new_container
            # indent marker doesn't need to match "real" YAML indent; just needs to be monotone
            stack.append((indent + 1, new_container))
            i += 1
            continue

        if not isinstance(container, dict):
            raise ValueError(f"Mapping entry found but container is not a dict near: {content!r}")
        container[key] = _parse_scalar(rest)
        i += 1

    debug(f"load_yaml_subset: loaded top-level keys={list(root.keys())}")
    return root


# ----------------------------
# Git helpers
# ----------------------------

@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str  # e.g. M, A, D, R100


def run_git(args: List[str]) -> str:
    debug(f"run_git: git {' '.join(args)}")
    p = subprocess.run(
        ["git"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def repo_root_from_git() -> Path:
    root = Path(run_git(["rev-parse", "--show-toplevel"]).strip())
    debug(f"repo_root_from_git: {root}")
    return root


def _git_ref_exists(ref: str) -> bool:
    try:
        run_git(["rev-parse", "--verify", ref])
        return True
    except Exception:
        return False


def list_changed_files(stage: str) -> Tuple[List[ChangedFile], Dict[str, Any]]:
    files: Dict[str, ChangedFile] = {}
    meta: Dict[str, Any] = {}

    def add_from_name_status(output: str) -> None:
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status = parts[0].strip()
            if status.startswith("R") and len(parts) >= 3:
                new_path = parts[2].strip()
                files[new_path] = ChangedFile(path=new_path, status=status)
            elif len(parts) >= 2:
                path = parts[1].strip()
                files[path] = ChangedFile(path=path, status=status)

    def add_untracked(output: str) -> None:
        for line in output.splitlines():
            p = line.strip()
            if not p:
                continue
            files[p] = ChangedFile(path=p, status="U")

    debug(f"list_changed_files: stage={stage}")
    if stage == "verification":
        add_from_name_status(run_git(["diff", "--cached", "--name-status"]))
        add_untracked(run_git(["ls-files", "--others", "--exclude-standard"]))
    elif stage == "coding":
        add_from_name_status(run_git(["diff", "--cached", "--name-status"]))
        add_from_name_status(run_git(["diff", "--name-status"]))
        add_untracked(run_git(["ls-files", "--others", "--exclude-standard"]))
    elif stage == "ci":
        base_candidates = ["origin/main", "origin/master", "main", "master"]
        base_ref: Optional[str] = None
        for cand in base_candidates:
            if _git_ref_exists(cand):
                base_ref = cand
                break

        meta["ci_base_ref"] = base_ref
        meta["ci_merge_base"] = None
        meta["ci_fallback_mode"] = None

        if base_ref is not None:
            try:
                merge_base = run_git(["merge-base", base_ref, "HEAD"]).strip()
                meta["ci_merge_base"] = merge_base
                add_from_name_status(run_git(["diff", "--name-status", f"{merge_base}..HEAD"]))
            except Exception as e:
                debug(f"ci merge-base or diff failed, fallback: {e}")
                base_ref = None
                meta["ci_base_ref"] = None
                meta["ci_merge_base"] = None

        if base_ref is None:
            # Fallback: HEAD~1..HEAD (if possible), else diff root
            try:
                run_git(["rev-parse", "--verify", "HEAD~1"])
                meta["ci_fallback_mode"] = "head~1"
                add_from_name_status(run_git(["diff", "--name-status", "HEAD~1..HEAD"]))
            except Exception:
                meta["ci_fallback_mode"] = "root"
                add_from_name_status(run_git(["diff", "--name-status", "--root", "HEAD"]))
    else:
        raise ValueError(f"Unknown stage: {stage}")

    debug(f"list_changed_files: count={len(files)}")
    return sorted(files.values(), key=lambda x: x.path), meta


# ----------------------------
# Path matching
# ----------------------------

def matches_any_glob(path: str, patterns: List[str]) -> bool:
    p = path.replace("\\", "/")
    for pat in patterns:
        pat2 = pat.replace("\\", "/")
        if fnmatch.fnmatch(p, pat2):
            return True
    return False


_GENERATED_OUTPUT_GLOBS = [
    ".intent-ops/intents/*/**/evidence/logs/validator-report.*.json",
]


def is_ignored_generated(path: str) -> bool:
    p = normalize_repo_rel_path(path)
    return matches_any_glob(p, _GENERATED_OUTPUT_GLOBS)


# ----------------------------
# Validation core
# ----------------------------

@dataclass
class Finding:
    level: str  # "fail" | "warn" | "info"
    code: str
    message: str
    path: Optional[str] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_summary(stage: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "tool": "intentops.validate",
        "stage": stage,
        "timestamp": now_iso(),
        "pass": True,
        "governance_level": None,
        "active_intent_id": None,
        "active_pack_path": None,
        "changed_files": [],
        "ignored_changed_files": [],
        "ci_base_ref": None,
        "ci_merge_base": None,
        "ci_fallback_mode": None,
        "findings": [],
        "debug": {},
    }


def add_debug(summary: Dict[str, Any], key: str, value: Any) -> None:
    if _DEBUG:
        summary.setdefault("debug", {})
        summary["debug"][key] = value


def add_fail(summary: Dict[str, Any], findings: List[Finding], code: str, msg: str, path: Optional[str] = None) -> None:
    findings.append(Finding("fail", code, msg, path))
    summary["pass"] = False


def normalize_repo_rel_path(path: str) -> str:
    p = str(path).replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    p = os.path.normpath(p).replace("\\", "/")
    return p


def load_framework_config(repo_root: Path) -> Dict[str, Any]:
    fpath = repo_root / ".intent-ops" / "framework" / "config" / "framework.yml"
    debug(f"load_framework_config: {fpath}")
    return load_yaml_subset(fpath)


def derive_framework_paths(framework: Dict[str, Any]) -> Dict[str, str]:
    paths = framework.get("paths", {}) if isinstance(framework.get("paths", {}), dict) else {}
    framework_root = normalize_repo_rel_path(paths.get("framework_root", ".intent-ops/framework"))
    intents_root = normalize_repo_rel_path(paths.get("intents_root", ".intent-ops/intents"))
    current_intent_file = normalize_repo_rel_path(paths.get("current_intent_file", ".intent-ops/intents/current-intent.json"))
    return {
        "framework_root": framework_root,
        "intents_root": intents_root,
        "current_intent_file": current_intent_file,
    }


def load_zones_config(repo_root: Path, framework_root: str) -> Dict[str, Any]:
    zpath = repo_root / framework_root / "config" / "zones.yml"
    debug(f"load_zones_config: {zpath}")
    return load_yaml_subset(zpath)


def load_current_intent(repo_root: Path, current_intent_file: str) -> Dict[str, Any]:
    cpath = repo_root / current_intent_file
    debug(f"load_current_intent: {cpath}")
    if not cpath.exists():
        raise FileNotFoundError(str(cpath))
    data = json.loads(cpath.read_text(encoding="utf-8"))
    debug(f"load_current_intent: keys={list(data.keys())}")
    return data


def resolve_active_pack(intents_root: Path, current_intent: Dict[str, Any]) -> Path:
    intents_root = intents_root.resolve()
    pack_rel = current_intent.get("active_pack_path")
    debug(f"resolve_active_pack: intents_root={intents_root} active_pack_path={pack_rel!r}")
    if not isinstance(pack_rel, str) or not pack_rel:
        raise ValueError("current-intent.json missing/invalid active_pack_path")
    pack_path = (intents_root / normalize_repo_rel_path(pack_rel)).resolve()
    debug(f"resolve_active_pack: resolved={pack_path}")
    if intents_root not in pack_path.parents and pack_path != intents_root:
        raise ValueError("active_pack_path escapes intents root")
    return pack_path


def load_intent_json(active_pack: Path) -> Dict[str, Any]:
    ipath = active_pack / "intent.json"
    debug(f"load_intent_json: {ipath}")
    if not ipath.exists():
        raise FileNotFoundError(str(ipath))
    data = json.loads(ipath.read_text(encoding="utf-8"))
    debug(f"load_intent_json: keys={list(data.keys())}")
    return data


def load_json_from_git_show(repo_rel_path: str, ref: str = "HEAD") -> Optional[Dict[str, Any]]:
    p = normalize_repo_rel_path(repo_rel_path)
    try:
        raw = run_git(["show", f"{ref}:{p}"])
    except Exception:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def effective_level(framework: Dict[str, Any]) -> str:
    lvl = framework.get("governance", {}).get("level", "var")
    lvl = str(lvl).strip().lower()
    if lvl not in ("var", "syn", "tyr"):
        lvl = "var"
    debug(f"effective_level: {lvl}")
    return lvl


def validate(stage: str) -> Tuple[bool, List[Finding], Dict[str, Any], Optional[Path], Optional[Path]]:
    summary = make_summary(stage)
    findings: List[Finding] = []
    active_pack: Optional[Path] = None
    repo_root: Optional[Path] = None

    # Repo root
    try:
        repo_root = repo_root_from_git()
    except Exception as e:
        add_fail(summary, findings, "REPO_ROOT_FAILED", f"Failed to locate repo root via git: {e}")
        summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
        return False, findings, summary, active_pack, repo_root

    add_debug(summary, "cwd", str(Path.cwd()))
    add_debug(summary, "repo_root", str(repo_root))

    # framework.yml
    try:
        framework = load_framework_config(repo_root)
    except Exception as e:
        debug(f"framework load exception: {e!r}")
        add_fail(summary, findings, "FRAMEWORK_LOAD_FAILED", f"Failed to load framework.yml: {e}")
        summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
        return False, findings, summary, active_pack, repo_root

    lvl = effective_level(framework)
    summary["governance_level"] = lvl

    fw_paths = derive_framework_paths(framework)
    framework_root_rel = fw_paths["framework_root"]
    intents_root_rel = fw_paths["intents_root"]
    current_intent_file_rel = fw_paths["current_intent_file"]

    add_debug(summary, "framework_root", framework_root_rel)
    add_debug(summary, "intents_root", intents_root_rel)
    add_debug(summary, "current_intent_file", current_intent_file_rel)

    # zones.yml
    try:
        zones = load_zones_config(repo_root, framework_root_rel)
    except Exception as e:
        debug(f"zones load exception: {e!r}")
        add_fail(summary, findings, "ZONES_LOAD_FAILED", f"Failed to load zones.yml: {e}")
        summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
        return False, findings, summary, active_pack, repo_root

    # current-intent.json
    try:
        current_intent = load_current_intent(repo_root, current_intent_file_rel)

        required_ci_keys = ("schema_version", "active_intent_id", "active_pack_path")
        missing_ci = [k for k in required_ci_keys if k not in current_intent]
        if missing_ci:
            raise ValueError(f"current-intent.json missing required keys: {', '.join(missing_ci)}")

        summary["active_intent_id"] = current_intent.get("active_intent_id")
        summary["active_pack_path"] = current_intent.get("active_pack_path")
        intents_root_abs = (repo_root.resolve() / intents_root_rel).resolve()
        active_pack = resolve_active_pack(intents_root_abs, current_intent)
    except Exception as e:
        debug(f"current intent resolve exception: {e!r}")
        add_fail(summary, findings, "CURRENT_INTENT_SCHEMA_INVALID", f"Failed to load/validate current intent control file: {e}")
        summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
        return False, findings, summary, active_pack, repo_root

    add_debug(summary, "active_pack_resolved", str(active_pack))

    if active_pack is None or not active_pack.exists():
        add_fail(summary, findings, "ACTIVE_PACK_MISSING", f"Active intent pack does not exist: {active_pack}")
        summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
        return False, findings, summary, active_pack, repo_root

    # intent.json
    try:
        intent = load_intent_json(active_pack)
    except Exception as e:
        debug(f"intent.json load exception: {e!r}")
        add_fail(summary, findings, "INTENT_LOAD_FAILED", f"Failed to load intent.json: {e}")
        summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
        return False, findings, summary, active_pack, repo_root

    # Minimal contract checks
    required_keys = ("schema_version", "intent_id", "goal", "status", "scope", "operations", "acceptance_criteria")
    for req_key in required_keys:
        if req_key not in intent:
            add_fail(summary, findings, "INTENT_SCHEMA_MINIMAL", f"intent.json missing required key: {req_key}")

    status = str(intent.get("status", "")).strip().lower()
    if status not in ("open", "closed"):
        add_fail(summary, findings, "INTENT_STATUS_INVALID", "intent.status must be either 'open' or 'closed'.")

    if current_intent.get("active_intent_id") != intent.get("intent_id"):
        add_fail(
            summary,
            findings,
            "ACTIVE_INTENT_ID_MISMATCH",
            "current-intent.json active_intent_id must match the active pack intent.json intent_id.",
            current_intent_file_rel,
        )

    scope = intent.get("scope", {}) if isinstance(intent.get("scope", {}), dict) else {}
    allowed_paths = scope.get("allowed_paths", [])
    forbidden_paths = scope.get("forbidden_paths", [])

    if not isinstance(allowed_paths, list) or not allowed_paths:
        add_fail(summary, findings, "INTENT_SCOPE_INVALID", "scope.allowed_paths must be a non-empty array")
        allowed_paths = []

    if forbidden_paths is None:
        forbidden_paths = []
    if not isinstance(forbidden_paths, list):
        add_fail(summary, findings, "INTENT_SCOPE_INVALID", "scope.forbidden_paths must be an array if present")
        forbidden_paths = []

    add_debug(summary, "scope_allowed_paths_count", len(allowed_paths))
    add_debug(summary, "scope_forbidden_paths_count", len(forbidden_paths))

    # Git changes
    try:
        changed, ci_meta = list_changed_files(stage)
    except Exception as e:
        debug(f"git diff exception: {e!r}")
        add_fail(summary, findings, "GIT_DIFF_FAILED", f"Failed to list changed files: {e}")
        summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
        return False, findings, summary, active_pack, repo_root

    if stage == "ci":
        summary["ci_base_ref"] = ci_meta.get("ci_base_ref")
        summary["ci_merge_base"] = ci_meta.get("ci_merge_base")
        summary["ci_fallback_mode"] = ci_meta.get("ci_fallback_mode")

    ignored: List[ChangedFile] = []
    effective_changed: List[ChangedFile] = []
    for c in changed:
        p = normalize_repo_rel_path(c.path)
        if is_ignored_generated(p):
            ignored.append(ChangedFile(path=p, status=c.status))
            continue
        effective_changed.append(ChangedFile(path=p, status=c.status))

    changed = sorted(effective_changed, key=lambda x: x.path)
    summary["changed_files"] = [{"path": c.path, "status": c.status} for c in changed]
    summary["ignored_changed_files"] = [{"path": c.path, "status": c.status} for c in ignored]

    # Dirty worktree gates
    if stage == "verification":
        try:
            unstaged = [normalize_repo_rel_path(x) for x in run_git(["diff", "--name-only"]).splitlines() if x.strip()]
            unstaged = [p for p in unstaged if not is_ignored_generated(p)]
        except Exception as e:
            unstaged = []
            debug(f"verification dirty gate failed to evaluate: {e!r}")

        if unstaged:
            add_fail(
                summary,
                findings,
                "VERIFICATION_DIRTY_WORKTREE",
                "verification stage requires a clean working tree (no unstaged tracked changes).",
                unstaged[0],
            )

    if stage == "ci":
        try:
            ci_unstaged = [normalize_repo_rel_path(x) for x in run_git(["diff", "--name-only"]).splitlines() if x.strip()]
            ci_unstaged = [p for p in ci_unstaged if not is_ignored_generated(p)]
        except Exception as e:
            ci_unstaged = []
            debug(f"ci dirty gate (unstaged) failed to evaluate: {e!r}")

        try:
            ci_untracked = [normalize_repo_rel_path(x) for x in run_git(["ls-files", "--others", "--exclude-standard"]).splitlines() if x.strip()]
            ci_untracked = [p for p in ci_untracked if not is_ignored_generated(p)]
        except Exception as e:
            ci_untracked = []
            debug(f"ci dirty gate (untracked) failed to evaluate: {e!r}")

        if ci_unstaged:
            add_fail(
                summary,
                findings,
                "CI_DIRTY_WORKTREE",
                "ci stage requires a clean working tree (no unstaged tracked changes).",
                ci_unstaged[0],
            )

        if ci_untracked:
            add_fail(
                summary,
                findings,
                "CI_UNTRACKED_PRESENT",
                "ci stage requires no untracked files (excluding ignored generated outputs).",
                ci_untracked[0],
            )

    # Zones
    zones_obj = zones.get("zones", {}) if isinstance(zones.get("zones", {}), dict) else {}
    purple_paths = (zones_obj.get("purple", {}) or {}).get("paths", []) or []
    orange_paths = (zones_obj.get("orange", {}) or {}).get("paths", []) or []

    add_debug(summary, "purple_paths", purple_paths)
    add_debug(summary, "orange_paths", orange_paths)

    repo_root_resolved = repo_root.resolve()
    intents_root = (repo_root_resolved / intents_root_rel).resolve()

    active_pack_rel_from_intents = os.path.relpath(active_pack.resolve(), intents_root).replace("\\", "/")
    active_pack_prefix = (active_pack_rel_from_intents.rstrip("/") + "/") if active_pack_rel_from_intents != "." else ""

    active_pack_repo_rel = normalize_repo_rel_path(os.path.relpath(active_pack.resolve(), repo_root_resolved))
    active_pack_repo_prefix = (active_pack_repo_rel.rstrip("/") + "/") if active_pack_repo_rel != "." else ""

    add_debug(summary, "intents_root", str(intents_root))
    add_debug(summary, "active_pack_rel_from_intents", active_pack_rel_from_intents)

    def is_under_active_pack(repo_rel_path: str) -> bool:
        pr = repo_rel_path.replace("\\", "/")
        full = (repo_root_resolved / pr).resolve()
        try:
            rel = os.path.relpath(full, intents_root).replace("\\", "/")
        except Exception:
            return False
        return rel == active_pack_rel_from_intents or rel.startswith(active_pack_prefix)

    kernel_upgrade = intent.get("kernel_upgrade", {}) if isinstance(intent.get("kernel_upgrade", {}), dict) else {}
    allow_purple_paths = kernel_upgrade.get("allow_purple_paths", [])
    if allow_purple_paths is None:
        allow_purple_paths = []
    if not isinstance(allow_purple_paths, list):
        allow_purple_paths = []
    allow_purple_paths = [str(x) for x in allow_purple_paths if isinstance(x, str) and str(x).strip()]

    current_intent_rel_norm = normalize_repo_rel_path(current_intent_file_rel)

    # ----------------------------
    # Patch 04: Intent lifecycle transactions
    # ----------------------------

    def is_under_repo_prefix(repo_rel_path: str, prefix: str) -> bool:
        pr = normalize_repo_rel_path(repo_rel_path)
        pre = normalize_repo_rel_path(prefix).rstrip("/")
        if not pre:
            return True
        return pr == pre or pr.startswith(pre + "/")

    current_intent_changed = any(c.path == current_intent_rel_norm for c in changed)

    # Closing transition detection for the *current* active pack
    active_intent_json_rel = normalize_repo_rel_path(f"{active_pack_repo_rel.rstrip('/')}/intent.json")
    head_intent = load_json_from_git_show(active_intent_json_rel, ref="HEAD")
    if head_intent is None:
        add_debug(summary, "head_intent_status_missing_assumed_open", True)
        head_status = "open"
    else:
        head_status = str(head_intent.get("status", "open")).strip().lower()

    working_status = str(intent.get("status", "")).strip().lower()

    if head_status == "closed" and working_status == "open":
        add_fail(
            summary,
            findings,
            "CLOSED_TO_OPEN_FORBIDDEN",
            "Closed intents may not be reopened (closed -> open is forbidden).",
            active_intent_json_rel,
        )

    close_transition = head_status == "open" and working_status == "closed"

    # Closed means immutable (based on HEAD)
    if head_status == "closed":
        for c in changed:
            if is_under_repo_prefix(c.path, active_pack_repo_prefix):
                add_fail(
                    summary,
                    findings,
                    "CLOSED_INTENT_IMMUTABLE",
                    "Active intent is closed in HEAD; files under the pack are immutable.",
                    c.path,
                )

    # Switch transaction detection (current-intent.json modified)
    if current_intent_changed:
        if stage == "coding":
            add_fail(
                summary,
                findings,
                "CURRENT_INTENT_CHANGED_IN_CODING",
                "current-intent.json may not be changed in coding stage.",
                current_intent_rel_norm,
            )
        # Strict switch transaction allowed change set
        for c in changed:
            if c.path == current_intent_rel_norm:
                continue
            if is_under_repo_prefix(c.path, active_pack_repo_prefix):
                continue
            add_fail(
                summary,
                findings,
                "SWITCH_TRANSACTION_MIXED_CHANGES",
                "When current-intent.json changes, only the new active pack and current-intent.json may change.",
                c.path,
            )

        # Target pack must be open
        if working_status == "closed":
            add_fail(
                summary,
                findings,
                "CLOSED_INTENT_NOT_ACTIVATABLE",
                "Cannot switch to an intent pack whose status is 'closed'.",
                active_intent_json_rel,
            )

        # Switch and close cannot be combined
        head_current_intent = load_json_from_git_show(current_intent_rel_norm, ref="HEAD")
        if isinstance(head_current_intent, dict):
            prev_pack_rel = head_current_intent.get("active_pack_path")
            if isinstance(prev_pack_rel, str) and prev_pack_rel.strip():
                prev_pack_abs = (intents_root / normalize_repo_rel_path(prev_pack_rel)).resolve()
                prev_pack_repo_rel = normalize_repo_rel_path(os.path.relpath(prev_pack_abs, repo_root_resolved))
                prev_intent_json_rel = normalize_repo_rel_path(f"{prev_pack_repo_rel.rstrip('/')}/intent.json")
                if any(c.path == prev_intent_json_rel for c in changed):
                    prev_head_intent = load_json_from_git_show(prev_intent_json_rel, ref="HEAD")
                    prev_working_intent: Optional[Dict[str, Any]] = None
                    try:
                        prev_working_intent = json.loads((repo_root_resolved / prev_intent_json_rel).read_text(encoding="utf-8"))
                    except Exception:
                        prev_working_intent = None
                    prev_head_status = str((prev_head_intent or {}).get("status", "open")).strip().lower()
                    prev_working_status = str((prev_working_intent or {}).get("status", "open")).strip().lower()
                    if prev_head_status == "open" and prev_working_status == "closed":
                        add_fail(
                            summary,
                            findings,
                            "SWITCH_AND_CLOSE_COMBINED",
                            "Switching active intent and closing the previous intent cannot be combined in one run.",
                            prev_intent_json_rel,
                        )

    # Close transaction strictness
    if close_transition:
        if current_intent_changed:
            add_fail(
                summary,
                findings,
                "SWITCH_AND_CLOSE_COMBINED",
                "Switching active intent and closing an intent cannot be combined in one run.",
                active_intent_json_rel,
            )

        if stage not in ("verification", "ci"):
            add_fail(
                summary,
                findings,
                "CLOSE_FORBIDDEN_STAGE",
                "Closing an intent (open -> closed) is only permitted in verification or ci stage.",
                active_intent_json_rel,
            )

        for c in changed:
            if c.path != active_intent_json_rel:
                add_fail(
                    summary,
                    findings,
                    "CLOSE_TRANSACTION_MIXED_CHANGES",
                    "When closing an intent, only the intent.json status flip is permitted (plus ignored generated outputs).",
                    c.path,
                )

    # Apply rules
    for c in changed:
        p = normalize_repo_rel_path(c.path)

        if is_ignored_generated(p):
            continue

        # Treat current-intent.json as a control file (not orange)
        if p == current_intent_rel_norm:
            if stage == "coding":
                add_fail(
                    summary,
                    findings,
                    "CURRENT_INTENT_CHANGED_IN_CODING",
                    "current-intent.json may not be changed in coding stage.",
                    p,
                )
            continue

        if matches_any_glob(p, purple_paths):
            if allow_purple_paths:
                if stage not in ("verification", "ci"):
                    add_fail(
                        summary,
                        findings,
                        "KERNEL_UPGRADE_FORBIDDEN_STAGE",
                        "Kernel upgrade allowlist for purple paths is only permitted in verification or ci stage.",
                        p,
                    )
                    continue
                if matches_any_glob(p, allow_purple_paths):
                    continue
                add_fail(
                    summary,
                    findings,
                    "PURPLE_TOUCHED_NOT_ALLOWLISTED",
                    "Purple zone file modified but not in kernel_upgrade.allow_purple_paths allowlist.",
                    p,
                )
                continue

            add_fail(summary, findings, "PURPLE_TOUCHED", "Framework (purple zone) must never be modified.", p)
            continue

        if matches_any_glob(p, orange_paths) and not is_under_active_pack(p):
            add_fail(
                summary,
                findings,
                "ORANGE_OUTSIDE_ACTIVE_PACK",
                "Only the active intent pack may be modified under intents (orange zone).",
                p,
            )
            continue

        if forbidden_paths and matches_any_glob(p, forbidden_paths):
            add_fail(
                summary,
                findings,
                "SCOPE_VIOLATION_FORBIDDEN",
                "Changed file matches scope.forbidden_paths (deny-wins).",
                p,
            )
            continue

        if allowed_paths and not matches_any_glob(p, allowed_paths):
            add_fail(
                summary,
                findings,
                "SCOPE_VIOLATION_NOT_ALLOWED",
                "Changed file is outside scope.allowed_paths for this intent.",
                p,
            )
            continue

    summary["findings"] = [{"level": f.level, "code": f.code, "message": f.message, "path": f.path} for f in findings]
    ok = summary["pass"] is True
    return ok, findings, summary, active_pack, repo_root


def write_report_to_pack(active_pack: Path, stage: str, report: Dict[str, Any]) -> Path:
    out = active_pack / "evidence" / "logs"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"validator-report.{stage}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_report_fallback(repo_root: Path, stage: str, report: Dict[str, Any]) -> Path:
    # If we can't resolve the active pack, still write somewhere deterministic.
    out = repo_root / ".intent-ops" / "intents"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"validator-report.{stage}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    global _DEBUG

    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["coding", "verification", "ci"])
    parser.add_argument("--debug", action="store_true", help="Enable debug logging to stderr and include debug fields in report.")
    args = parser.parse_args()

    _DEBUG = bool(args.debug)
    debug(f"started: stage={args.stage} debug={_DEBUG}")

    ok, _findings, report, active_pack, repo_root = validate(args.stage)

    # Write report
    try:
        if active_pack is not None and active_pack.exists():
            p = write_report_to_pack(active_pack, args.stage, report)
            debug(f"wrote report to pack: {p}")
        elif repo_root is not None and repo_root.exists():
            p = write_report_fallback(repo_root, args.stage, report)
            debug(f"wrote fallback report: {p}")
        else:
            debug("report not written: no active_pack and no repo_root")
    except Exception as e:
        debug(f"failed to write report: {e!r}")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
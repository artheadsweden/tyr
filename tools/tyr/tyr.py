#!/usr/bin/env python3
"""Tyr deterministic validator CLI (v0.5 foundation).

This tool is intentionally stdlib-only and deterministic.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


EXIT_PASS = 0
EXIT_ROUTING_INVALID = 10
EXIT_ARTIFACT_INVALID = 20
EXIT_ZONE_VIOLATION = 30
EXIT_RED_OP_VIOLATION = 40
EXIT_PLAN_VIOLATION = 50
EXIT_YELLOW_AUTO = 60
EXIT_MANIFEST_MISMATCH = 70
EXIT_UNKNOWN = 80


@dataclasses.dataclass(frozen=True)
class ValidationMessage:
    code: str
    message: str
    path: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclasses.dataclass
class ValidationReport:
    ok: bool
    stage: str
    exit_code: int
    intent_folder: Optional[str]
    base_sha: Optional[str]
    working_sha: Optional[str]
    changed_files: List[Dict[str, Any]]
    errors: List[ValidationMessage]
    warnings: List[ValidationMessage]
    timestamp_utc: str

    def to_json_obj(self) -> Dict[str, Any]:
        def msg_to_obj(m: ValidationMessage) -> Dict[str, Any]:
            obj: Dict[str, Any] = {"code": m.code, "message": m.message}
            if m.path is not None:
                obj["path"] = m.path
            if m.details is not None:
                obj["details"] = m.details
            return obj

        return {
            "validator_report_version": "validator_report.v1",
            "ok": self.ok,
            "stage": self.stage,
            "exit_code": self.exit_code,
            "intent_folder": self.intent_folder,
            "base_sha": self.base_sha,
            "working_sha": self.working_sha,
            "changed_files": self.changed_files,
            "errors": [msg_to_obj(e) for e in self.errors],
            "warnings": [msg_to_obj(w) for w in self.warnings],
            "timestamp_utc": self.timestamp_utc,
        }


class TyrValidatorError(Exception):
    pass


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_git(repo_root: Path, args: Sequence[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise TyrValidatorError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _repo_root_from_cwd() -> Path:
    cwd = Path.cwd()
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=str(cwd), text=True)
    except Exception as e:  # noqa: BLE001
        raise TyrValidatorError("Not inside a git repository") from e
    return Path(out.strip())


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise TyrValidatorError(f"Missing required JSON file: {path}") from e
    except json.JSONDecodeError as e:
        raise TyrValidatorError(f"Invalid JSON in {path}: {e}") from e


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _strip_yaml_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def _parse_scalar(value: str) -> Any:
    v = value.strip()
    if v == "":
        return ""
    if v in {"null", "Null", "NULL", "~"}:
        return None
    if v in {"true", "True", "TRUE"}:
        return True
    if v in {"false", "False", "FALSE"}:
        return False
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if inner == "":
            return []
        parts = [p.strip() for p in inner.split(",")]
        return [_parse_scalar(p) for p in parts]
    # int
    if re.fullmatch(r"-?[0-9]+", v):
        try:
            return int(v)
        except Exception:  # noqa: BLE001
            pass
    # float
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", v):
        try:
            return float(v)
        except Exception:  # noqa: BLE001
            pass
    return v


def _load_simple_yaml(text: str) -> Any:
    """Parse a small, safe subset of YAML (dict/list/scalars).

    Supported:
    - indentation-based dict nesting
    - lists introduced with '- '
    - scalars: strings, ints, bool, null, [a, b] inline lists

    This is intentionally limited to keep the validator stdlib-only.
    """

    lines: List[Tuple[int, str]] = []
    for raw in text.splitlines():
        raw = _strip_yaml_comment(raw).rstrip("\n")
        if raw.strip() == "":
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw[:indent]:
            raise TyrValidatorError("Tabs are not supported in YAML")
        lines.append((indent, raw.strip()))

    idx = 0

    def parse_block(expected_indent: int) -> Any:
        nonlocal idx

        # Determine whether next block is list or dict
        if idx >= len(lines):
            return {}
        indent, content = lines[idx]
        if indent < expected_indent:
            return {}
        if indent > expected_indent:
            raise TyrValidatorError("Invalid YAML indentation")

        if content.startswith("-"):
            items: List[Any] = []
            while idx < len(lines):
                indent2, content2 = lines[idx]
                if indent2 != expected_indent:
                    break
                if not content2.startswith("-"):
                    break
                item_content = content2[1:].lstrip(" ")
                idx += 1
                if item_content == "":
                    # nested structure
                    item = parse_block(expected_indent + 2)
                    items.append(item)
                    continue

                # inline dict on list item: "- key: value"
                if ":" in item_content:
                    key, rest = item_content.split(":", 1)
                    key = str(_parse_scalar(key.strip()))
                    rest = rest.strip()
                    d: Dict[str, Any] = {}
                    if rest == "":
                        d[key] = parse_block(expected_indent + 2)
                    else:
                        d[key] = _parse_scalar(rest)

                    # consume additional kv pairs at deeper indent
                    while idx < len(lines):
                        indent3, content3 = lines[idx]
                        if indent3 < expected_indent + 2:
                            break
                        if indent3 > expected_indent + 2:
                            raise TyrValidatorError("Invalid YAML indentation")
                        if content3.startswith("-"):
                            break
                        if ":" not in content3:
                            raise TyrValidatorError("Expected key: value")
                        k2, v2 = content3.split(":", 1)
                        k2 = str(_parse_scalar(k2.strip()))
                        v2 = v2.strip()
                        idx += 1
                        if v2 == "":
                            d[k2] = parse_block(expected_indent + 4)
                        else:
                            d[k2] = _parse_scalar(v2)
                    items.append(d)
                else:
                    items.append(_parse_scalar(item_content))
            return items

        # dict
        d2: Dict[str, Any] = {}
        while idx < len(lines):
            indent2, content2 = lines[idx]
            if indent2 < expected_indent:
                break
            if indent2 > expected_indent:
                raise TyrValidatorError("Invalid YAML indentation")
            if content2.startswith("-"):
                break
            if ":" not in content2:
                raise TyrValidatorError(f"Expected key: value, got: {content2}")
            key, rest = content2.split(":", 1)
            key = str(_parse_scalar(key.strip()))
            rest = rest.strip()
            idx += 1
            if rest == "":
                d2[key] = parse_block(expected_indent + 2)
            else:
                d2[key] = _parse_scalar(rest)
        return d2

    root = parse_block(0)
    return root


def _read_yaml_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise TyrValidatorError(f"Missing required YAML file: {path}") from e
    return _load_simple_yaml(text)


def _compile_root_anchored_glob(pattern: str) -> re.Pattern[str]:
    """Convert root-anchored glob to a regex.

    Supported tokens:
    - '*' within a segment (no '/')
    - '**' across segments
    - '?' within a segment
    - character classes [] are passed through (best effort)

    The match is for the full normalized repo-relative path.
    """

    pat = pattern.strip()
    if pat.startswith("./"):
        pat = pat[2:]
    if pat.startswith("/"):
        pat = pat[1:]

    i = 0
    out = "^"
    while i < len(pat):
        ch = pat[i]
        if ch == "*":
            if i + 1 < len(pat) and pat[i + 1] == "*":
                out += ".*"
                i += 2
            else:
                out += "[^/]*"
                i += 1
            continue
        if ch == "?":
            out += "[^/]"
            i += 1
            continue
        if ch == "[":
            # best-effort: include until closing bracket
            j = pat.find("]", i + 1)
            if j == -1:
                out += re.escape(ch)
                i += 1
            else:
                out += pat[i : j + 1]
                i = j + 1
            continue
        out += re.escape(ch)
        i += 1

    out += "$"
    return re.compile(out)


def _normalize_repo_path(p: str) -> str:
    p2 = p.replace("\\", "/")
    while p2.startswith("./"):
        p2 = p2[2:]
    if p2.startswith("/"):
        p2 = p2[1:]
    return p2


def _parse_plan_scopes(plan_path: Path) -> Tuple[List[str], List[str], List[str]]:
    """Extract allowed_paths, forbidden_paths, expected_zones from development-plan.md.

    This is a very small parser tailored to the current plan format.
    """

    text = plan_path.read_text(encoding="utf-8")
    allowed: List[str] = []
    forbidden: List[str] = []
    expected_zones: List[str] = []

    current: Optional[str] = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("allowed_paths:"):
            current = "allowed"
            continue
        if stripped.startswith("forbidden_paths:"):
            current = "forbidden"
            continue
        if stripped.startswith("expected_zones:"):
            # expected_zones: [orange]
            _, rest = stripped.split(":", 1)
            expected_zones = [str(z) for z in _parse_scalar(rest) or []]
            current = None
            continue

        m = re.match(r"^-\s+(.+)$", stripped)
        if not m:
            continue
        item = m.group(1).strip()
        # remove trailing comments
        item = _strip_yaml_comment(item).strip()
        if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
            item = item[1:-1]

        if current == "allowed":
            allowed.append(item)
        elif current == "forbidden":
            forbidden.append(item)

    return allowed, forbidden, expected_zones


def _zone_for_path(path: str, zones_cfg: Dict[str, Any]) -> str:
    folder_zones: Dict[str, Any] = zones_cfg.get("folder_zones", {}) or {}
    file_overrides: Dict[str, Any] = zones_cfg.get("file_overrides", {}) or {}

    path_n = _normalize_repo_path(path)
    if path_n in file_overrides:
        return str(file_overrides[path_n])

    best_prefix = ""
    best_zone = None
    for prefix, zone in folder_zones.items():
        pref = _normalize_repo_path(str(prefix))
        if pref == "":
            # root
            if best_zone is None:
                best_zone = str(zone)
                best_prefix = ""
            continue
        if not pref.endswith("/"):
            pref = pref + "/"
        if path_n.startswith(pref) and len(pref) > len(best_prefix):
            best_prefix = pref
            best_zone = str(zone)

    if best_zone is None:
        return "yellow-auto"
    return best_zone


def _classified_parent_prefixes(zones_cfg: Dict[str, Any]) -> List[str]:
    """Return normalized classified folder prefixes excluding the root "" entry.

    v0.5 yellow-auto semantics treat new folders as quarantine unless they are under
    an explicitly classified parent folder (e.g. docs/, .id-sdlc/). The root "" zone
    is not considered a sufficient classification for new folders.
    """

    folder_zones: Dict[str, Any] = zones_cfg.get("folder_zones", {}) or {}
    prefixes: List[str] = []
    for k in folder_zones.keys():
        pref = _normalize_repo_path(str(k))
        if pref == "":
            continue
        if not pref.endswith("/"):
            pref += "/"
        prefixes.append(pref)
    prefixes.sort(key=len, reverse=True)
    return prefixes


def _is_under_any_prefix(path: str, prefixes: Sequence[str]) -> bool:
    p = _normalize_repo_path(path)
    for pref in prefixes:
        if p.startswith(pref):
            return True
    return False


def _git_diff_name_status_z(repo_root: Path, diff_args: Sequence[str]) -> List[Tuple[str, str, Optional[str]]]:
    """Return list of (change_type, path, extra_path) for git diff --name-status -z."""

    out = _run_git(repo_root, ["diff", "--name-status", "-z", *diff_args])
    parts = out.split("\0")
    # -z format is NUL-delimited tokens:
    #   <status>\0<path>\0
    # For renames/copies:
    #   R<score>\0<old>\0<new>\0
    i = 0
    results: List[Tuple[str, str, Optional[str]]] = []
    while i < len(parts):
        status = parts[i]
        if status == "":
            i += 1
            continue
        if i + 1 >= len(parts):
            raise TyrValidatorError("Unexpected git diff -z format")
        change = status[0]
        if change == "R":
            if i + 2 >= len(parts):
                raise TyrValidatorError("Unexpected rename format")
            old_path = parts[i + 1]
            new_path = parts[i + 2]
            if old_path == "" or new_path == "":
                raise TyrValidatorError("Unexpected rename format")
            results.append(("R", _normalize_repo_path(old_path), _normalize_repo_path(new_path)))
            i += 3
            continue

        path1 = parts[i + 1]
        if path1 == "":
            raise TyrValidatorError("Unexpected git diff -z format")
        results.append((change, _normalize_repo_path(path1), None))
        i += 2
    # stable sort
    results.sort(key=lambda t: (t[0], t[1], t[2] or ""))
    return results


def _git_untracked_files(repo_root: Path) -> List[str]:
    out = _run_git(repo_root, ["ls-files", "--others", "--exclude-standard", "-z"])
    parts = [p for p in out.split("\0") if p]
    return sorted({_normalize_repo_path(p) for p in parts})


def _detect_new_directories(repo_root: Path, base_sha: str, changed_paths: Iterable[str]) -> List[str]:
    """Return a stable list of newly created directories relative to base_sha.

    This is best-effort: it checks whether a directory tree existed at base_sha.
    """

    cache: Dict[str, bool] = {}

    def existed_at_base(dir_path: str) -> bool:
        if dir_path in cache:
            return cache[dir_path]
        try:
            _run_git(repo_root, ["cat-file", "-e", f"{base_sha}:{dir_path}"])
            cache[dir_path] = True
        except TyrValidatorError:
            cache[dir_path] = False
        return cache[dir_path]

    new_dirs: set[str] = set()
    for p in changed_paths:
        p_n = _normalize_repo_path(p)
        parent = os.path.dirname(p_n)
        if parent in {"", "."}:
            continue
        segments = parent.split("/")
        for k in range(1, len(segments) + 1):
            d = "/".join(segments[:k])
            if not existed_at_base(d):
                new_dirs.add(d)

    return sorted(new_dirs)


def _read_governance_level(governance_cfg: Dict[str, Any]) -> int:
    for key in ("governance_level", "level"):
        if key in governance_cfg:
            try:
                return int(governance_cfg[key])
            except Exception:  # noqa: BLE001
                return 1
    return 1


def _active_intent_folder(repo_root: Path) -> Path:
    pointer = repo_root / ".id-sdlc" / "current-intent.json"
    current = _read_json(pointer)
    folder = current.get("folder")
    if not isinstance(folder, str) or folder.strip() == "":
        raise TyrValidatorError("current-intent.json missing valid 'folder'")
    intent_dir = repo_root / ".id-sdlc" / "intent" / folder
    if not intent_dir.exists() or not intent_dir.is_dir():
        raise TyrValidatorError(f"Active intent folder does not exist: {intent_dir}")
    return intent_dir


def validate(stage: str) -> ValidationReport:
    repo_root = _repo_root_from_cwd()

    errors: List[ValidationMessage] = []
    warnings: List[ValidationMessage] = []

    intent_folder: Optional[str] = None
    base_sha: Optional[str] = None
    working_sha: Optional[str] = None
    changed_files_report: List[Dict[str, Any]] = []

    try:
        governance_cfg = _read_yaml_file(repo_root / ".id-sdlc" / "governance-config.yml")
        zones_cfg = _read_yaml_file(repo_root / ".id-sdlc" / "zones.yml")
        red_ops_cfg = _read_yaml_file(repo_root / ".id-sdlc" / "red_operations.yml")

        level = _read_governance_level(governance_cfg)

        intent_dir = _active_intent_folder(repo_root)
        intent_folder = intent_dir.name

        ignore_paths = {
            f".id-sdlc/intent/{intent_folder}/validator-report.json",
            f".id-sdlc/intent/{intent_folder}/validator-report.md",
        }

        # Required artifacts
        required = ["intent.md", "metadata.json"]
        for r in required:
            if not (intent_dir / r).exists():
                errors.append(ValidationMessage("MISSING_ARTIFACT", f"Missing required artifact: {r}", path=str(intent_dir / r)))

        manifest_path = intent_dir / "change-manifest.json"
        manifest: Optional[Dict[str, Any]] = None
        if manifest_path.exists():
            manifest = _read_json(manifest_path)

        if level >= 3 and manifest is None:
            errors.append(ValidationMessage("MISSING_MANIFEST", "change-manifest.json required at governance level 3+", path=str(manifest_path)))

        if errors:
            raise TyrValidatorError("Artifact contract invalid")

        # Determine base/working SHAs
        if manifest is not None and isinstance(manifest.get("base_sha"), str):
            base_sha = manifest["base_sha"]
        else:
            # best-effort base for verification/ci is parent
            try:
                base_sha = _run_git(repo_root, ["rev-parse", "HEAD^"]).strip()
            except TyrValidatorError:
                base_sha = _run_git(repo_root, ["rev-parse", "HEAD"]).strip()

        head_sha = _run_git(repo_root, ["rev-parse", "HEAD"]).strip()

        if stage == "coding":
            # If manifest says working_sha is null, we still validate the worktree against base_sha.
            working_sha = None
            if manifest is not None and manifest.get("working_sha") not in (None, ""):
                if isinstance(manifest.get("working_sha"), str):
                    working_sha = manifest["working_sha"]
            # Diff worktree and index against base_sha, plus untracked files.
            unstaged = _git_diff_name_status_z(repo_root, [base_sha])
            staged = _git_diff_name_status_z(repo_root, ["--cached", base_sha])
            untracked = [("A", p, None) for p in _git_untracked_files(repo_root)]
            diff_entries = sorted(set(unstaged + staged + untracked), key=lambda t: (t[0], t[1], t[2] or ""))
        else:
            working_sha = head_sha
            diff_entries = _git_diff_name_status_z(repo_root, [f"{base_sha}..{head_sha}"])

        # Do not treat validator-generated reports as "changes" for enforcement.
        filtered: List[Tuple[str, str, Optional[str]]] = []
        for ch, p1, p2 in diff_entries:
            if ch == "R":
                if p2 in ignore_paths or p1 in ignore_paths:
                    continue
            else:
                if p1 in ignore_paths:
                    continue
            filtered.append((ch, p1, p2))
        diff_entries = filtered

        # Unsupported rename semantics unless manifest uses explicit "old -> new" form.
        for ch, p1, p2 in diff_entries:
            if ch == "R" and (p2 is None or p2 == ""):
                raise TyrValidatorError("Rename diff entry missing new path")

        changed_paths = []
        for ch, p1, p2 in diff_entries:
            if ch == "R":
                changed_paths.append(f"{p1} -> {p2}")
            else:
                changed_paths.append(p1)

        # Load plan scopes (optional)
        plan_path = intent_dir / "development-plan.md"
        allowed_paths: List[str] = []
        forbidden_paths: List[str] = []
        expected_zones: List[str] = []
        if plan_path.exists():
            allowed_paths, forbidden_paths, expected_zones = _parse_plan_scopes(plan_path)

        if not allowed_paths:
            # fallback: intent folder boundaries
            allowed_paths = [f".id-sdlc/intent/{intent_folder}/**", ".id-sdlc/current-intent.json"]

        allowed_re = [_compile_root_anchored_glob(p) for p in allowed_paths]
        forbidden_re = [_compile_root_anchored_glob(p) for p in forbidden_paths]

        # Zone + plan enforcement
        zones_dict = zones_cfg if isinstance(zones_cfg, dict) else {}

        # Determine new directories (best-effort) and apply v0.5 yellow-auto quarantine semantics.
        # New folders default to zones.defaults.new_folder_zone unless they are under an explicitly
        # classified parent prefix in folder_zones (excluding root "").
        changed_for_newdir = [p1 if " -> " not in p1 else p1.split(" -> ", 1)[1] for p1 in changed_paths]
        new_dirs = _detect_new_directories(repo_root, base_sha, changed_for_newdir)
        new_folder_zone = str(((zones_dict.get("defaults") or {}).get("new_folder_zone")) or "yellow-auto")
        classified_prefixes = _classified_parent_prefixes(zones_dict)
        new_dirs_set = set(new_dirs)

        for ch, p1, p2 in diff_entries:
            if ch == "R":
                display_path = f"{p1} -> {p2}"
                match_path = p2 or p1
                zone = _zone_for_path(match_path, zones_dict)
            else:
                display_path = p1
                match_path = p1
                zone = _zone_for_path(match_path, zones_dict)

            # Apply quarantine zone override for files under newly created directories, unless they
            # are already under an explicitly classified parent prefix.
            parent = os.path.dirname(_normalize_repo_path(match_path))
            under_new_dir = False
            if parent not in {"", "."}:
                segments = parent.split("/")
                for k in range(1, len(segments) + 1):
                    d = "/".join(segments[:k])
                    if d in new_dirs_set:
                        under_new_dir = True
                        break
            if under_new_dir and not _is_under_any_prefix(match_path, classified_prefixes):
                zone = new_folder_zone

            allowed_ok = any(r.match(match_path) for r in allowed_re)
            forbidden_hit = any(r.match(match_path) for r in forbidden_re)

            if not allowed_ok:
                errors.append(ValidationMessage("PLAN_ALLOWED_VIOLATION", "Changed file is outside allowed_paths", path=display_path))
            if forbidden_hit:
                errors.append(ValidationMessage("PLAN_FORBIDDEN_VIOLATION", "Changed file matches forbidden_paths", path=display_path))

            if expected_zones and zone not in expected_zones:
                errors.append(
                    ValidationMessage(
                        "ZONE_EXPECTATION_VIOLATION",
                        "Changed file touches a zone not listed in expected_zones",
                        path=display_path,
                        details={"zone": zone, "expected_zones": expected_zones},
                    )
                )

            changed_files_report.append({"path": display_path, "change_type": ch, "zone": zone})

        # yellow-auto quarantine enforcement
        yellow_auto_touches = [e for e in changed_files_report if e.get("zone") == "yellow-auto"]
        if yellow_auto_touches:
            details = {"paths": [e.get("path") for e in yellow_auto_touches], "new_paths": new_dirs}
            if level >= 2:
                errors.append(
                    ValidationMessage(
                        "YELLOW_AUTO_QUARANTINE",
                        "Changes touch yellow-auto quarantine. Human must classify new folders in zones.yml before merge.",
                        details=details,
                    )
                )
            else:
                warnings.append(
                    ValidationMessage(
                        "YELLOW_AUTO_QUARANTINE",
                        "Changes touch yellow-auto quarantine (warning only because governance level < 2).",
                        details=details,
                    )
                )

        # red operations detection (path/pattern based)
        detected_red_ops: List[str] = []
        ops = []
        if isinstance(red_ops_cfg, dict):
            ops = red_ops_cfg.get("operations", []) or []
        for op in ops:
            if not isinstance(op, dict):
                continue
            op_id = op.get("id")
            match = op.get("match") or {}
            match_paths = match.get("paths") or []
            match_patterns = match.get("patterns") or []
            if not isinstance(op_id, str):
                continue

            for entry in changed_files_report:
                p = entry.get("path")
                if not isinstance(p, str):
                    continue
                # renames use "old -> new"; match against both
                candidates = [p]
                if " -> " in p:
                    old, new = p.split(" -> ", 1)
                    candidates = [old, new]

                hit = False
                for c in candidates:
                    c_n = _normalize_repo_path(c)
                    for mp in match_paths:
                        mp_s = _normalize_repo_path(str(mp))
                        if mp_s.endswith("/"):
                            if c_n.startswith(mp_s):
                                hit = True
                                break
                        else:
                            if c_n == mp_s:
                                hit = True
                                break
                    if hit:
                        break

                    c_low = c_n.lower()
                    for token in match_patterns:
                        t = str(token).lower()
                        if t and t in c_low:
                            hit = True
                            break
                    if hit:
                        break

                if hit:
                    detected_red_ops.append(op_id)
                    break

        detected_red_ops = sorted(set(detected_red_ops))

        manifest_red_ops: List[str] = []
        if manifest is not None:
            ro = manifest.get("red_ops_observed")
            if isinstance(ro, list):
                manifest_red_ops = [str(x) for x in ro]

        if level >= 3:
            missing_decl = [x for x in detected_red_ops if x not in set(manifest_red_ops)]
            if missing_decl:
                errors.append(
                    ValidationMessage(
                        "RED_OP_UNDECLARED",
                        "Validator detected red operations by path match that are not declared in change-manifest.json",
                        details={"detected": detected_red_ops, "declared": manifest_red_ops},
                    )
                )

            # Spec says manifest red_ops_observed must be a subset of path-based detection.
            extra_decl = [x for x in manifest_red_ops if x not in set(detected_red_ops)]
            if extra_decl:
                errors.append(
                    ValidationMessage(
                        "MANIFEST_RED_OPS_NOT_SUBSET",
                        "change-manifest.json declares red ops not detected by validator path matching",
                        details={"detected": detected_red_ops, "declared": manifest_red_ops},
                    )
                )

        # manifest mismatch
        if manifest is not None and level >= 3:
            if manifest.get("artifact_schema_version") != "change_manifest.v1":
                errors.append(ValidationMessage("MANIFEST_SCHEMA", "Unsupported change-manifest schema version"))

            manifest_files = manifest.get("changed_files")
            if not isinstance(manifest_files, list):
                errors.append(ValidationMessage("MANIFEST_FORMAT", "changed_files must be a list"))
            else:
                # normalize to (change_type, path, extra)
                mf: List[Tuple[str, str, Optional[str]]] = []
                zone_mismatches: List[Dict[str, Any]] = []
                for item in manifest_files:
                    if not isinstance(item, dict):
                        continue
                    ct = str(item.get("change_type"))
                    p = item.get("path")
                    zexp = item.get("zone_expected")
                    if not isinstance(p, str):
                        continue
                    p_n = _normalize_repo_path(p)
                    if ct == "R":
                        if " -> " not in p_n:
                            errors.append(ValidationMessage("MANIFEST_RENAME", "Rename entries must use 'old -> new' in path field", path=p_n))
                            continue
                        old, new = p_n.split(" -> ", 1)
                        mf.append(("R", old.strip(), new.strip()))
                        zone_actual = _zone_for_path(new.strip(), zones_dict)
                    else:
                        mf.append((ct, p_n, None))
                        zone_actual = _zone_for_path(p_n, zones_dict)

                    if zexp is not None and str(zexp) != str(zone_actual):
                        zone_mismatches.append({"path": p_n, "zone_expected": zexp, "zone_actual": zone_actual})

                if zone_mismatches:
                    errors.append(
                        ValidationMessage(
                            "MANIFEST_ZONE_MISMATCH",
                            "change-manifest.json zone_expected does not match deterministic zone mapping",
                            details={"mismatches": zone_mismatches},
                        )
                    )

                df = diff_entries
                if sorted(mf) != sorted(df):
                    errors.append(
                        ValidationMessage(
                            "MANIFEST_DIFF_MISMATCH",
                            "change-manifest.json does not match git diff exactly",
                            details={"diff": df, "manifest": sorted(mf)},
                        )
                    )

            # base/working SHA checks
            if isinstance(manifest.get("base_sha"), str) and manifest.get("base_sha") != base_sha:
                errors.append(
                    ValidationMessage(
                        "MANIFEST_BASE_SHA_MISMATCH",
                        "change-manifest.json base_sha does not match validator base_sha",
                        details={"manifest": manifest.get("base_sha"), "validator": base_sha},
                    )
                )
            if stage in {"verification", "ci"}:
                if manifest.get("working_sha") is None:
                    errors.append(ValidationMessage("MANIFEST_WORKING_SHA_MISSING", "working_sha must be set for verification/ci"))
                elif isinstance(manifest.get("working_sha"), str) and manifest.get("working_sha") != head_sha:
                    errors.append(
                        ValidationMessage(
                            "MANIFEST_WORKING_SHA_MISMATCH",
                            "change-manifest.json working_sha must match HEAD for verification/ci",
                            details={"manifest": manifest.get("working_sha"), "head": head_sha},
                        )
                    )

            # new_paths check
            m_new_paths = manifest.get("new_paths")
            if isinstance(m_new_paths, list):
                m_new_paths_norm = sorted({_normalize_repo_path(str(x)) for x in m_new_paths})
                if m_new_paths_norm != sorted(new_dirs):
                    errors.append(
                        ValidationMessage(
                            "MANIFEST_NEW_PATHS_MISMATCH",
                            "change-manifest.json new_paths does not match detected new directories",
                            details={"manifest": m_new_paths_norm, "detected": new_dirs},
                        )
                    )

        # Decide exit code based on error categories (deterministic precedence)
        exit_code = EXIT_PASS
        ok = True
        if errors:
            ok = False
            codes = {e.code for e in errors}
            if any(c.startswith("MISSING_") for c in codes) or any(c == "MISSING_ARTIFACT" for c in codes):
                exit_code = EXIT_ARTIFACT_INVALID
            elif any(c.startswith("MANIFEST_") for c in codes):
                exit_code = EXIT_MANIFEST_MISMATCH
            elif any(c.startswith("YELLOW_AUTO") for c in codes):
                exit_code = EXIT_YELLOW_AUTO
            elif any(c.startswith("RED_") for c in codes):
                exit_code = EXIT_RED_OP_VIOLATION
            elif any(c.startswith("ZONE_") for c in codes):
                exit_code = EXIT_ZONE_VIOLATION
            elif any(c.startswith("PLAN_") for c in codes):
                exit_code = EXIT_PLAN_VIOLATION
            else:
                exit_code = EXIT_UNKNOWN

        report = ValidationReport(
            ok=ok,
            stage=stage,
            exit_code=exit_code,
            intent_folder=intent_folder,
            base_sha=base_sha,
            working_sha=working_sha,
            changed_files=changed_files_report,
            errors=errors,
            warnings=warnings,
            timestamp_utc=_now_utc_iso(),
        )

        out_json = intent_dir / "validator-report.json"
        _write_json(out_json, report.to_json_obj())

        if stage == "ci":
            # CI-friendly single-line output
            print(json.dumps({"ok": report.ok, "exit_code": report.exit_code, "intent_folder": report.intent_folder}))
        else:
            print(json.dumps(report.to_json_obj(), indent=2, sort_keys=True))

        return report

    except TyrValidatorError as e:
        # If routing is broken we may not know intent_dir; print minimal and exit.
        msg = str(e)
        if "current-intent" in msg or "Active intent folder" in msg:
            exit_code = EXIT_ROUTING_INVALID
        elif "Artifact contract" in msg or "Missing required" in msg:
            exit_code = EXIT_ARTIFACT_INVALID
        else:
            exit_code = EXIT_UNKNOWN

        report = ValidationReport(
            ok=False,
            stage=stage,
            exit_code=exit_code,
            intent_folder=intent_folder,
            base_sha=base_sha,
            working_sha=working_sha,
            changed_files=changed_files_report,
            errors=[ValidationMessage("VALIDATOR_EXCEPTION", msg)],
            warnings=warnings,
            timestamp_utc=_now_utc_iso(),
        )

        if intent_folder:
            try:
                out_json = repo_root / ".id-sdlc" / "intent" / intent_folder / "validator-report.json"
                _write_json(out_json, report.to_json_obj())
            except Exception:  # noqa: BLE001
                pass

        print(json.dumps(report.to_json_obj(), indent=2, sort_keys=True))
        return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="tyr", description="Tyr deterministic validator (v0.5)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate current repo state against intent + governance")
    p_validate.add_argument("--stage", choices=["coding", "verification", "ci"], required=True)

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "validate":
        report = validate(stage=args.stage)
        return int(report.exit_code)

    return EXIT_UNKNOWN


if __name__ == "__main__":
    raise SystemExit(main())

"""nexus_engine.py
Headless Nexus engine: planning, safety, execution, undo.
UI-agnostic, suitable for CLI, Tk, Qt, or web frontends.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Callable, Dict, List, Optional, Tuple


# -------------------- Data models --------------------

@dataclass(slots=True)
class MoveItem:
    src: Path
    planned_dst: Path
    final_dst: Path
    category: str
    source_root: Path
    relpath: Path
    size: int
    mtime: float
    duplicate_group: str = ""


@dataclass(slots=True)
class Plan:
    moves: List[MoveItem] = field(default_factory=list)
    duplicates: Dict[str, List[Path]] = field(default_factory=dict)
    duplicate_deletes: List[Path] = field(default_factory=list)
    ignored_files: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    hash_failures: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.moves and not self.duplicate_deletes


@dataclass(slots=True)
class EngineState:
    sources: List[Path] = field(default_factory=list)
    destination: Optional[Path] = None
    rules_text: str = ""
    dry_run: bool = True
    include_duplicates: bool = True
    organize_mode: str = "category"  # or "mirror" / "foldersort"
    cloud_safe_mode: bool = True
    batch_limit: int = 500
    last_plan: Optional[Plan] = None
    last_manifest: Optional[Path] = None


# -------------------- Constants & helpers --------------------

SYSTEM_FILES = {
    "thumbs.db",
    "desktop.ini",
    ".ds_store",
    ".localized",
}

PROTECTED_DIRS = {
    ".git",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
}

DEFAULT_RULES = {
    ".txt": "DOCS",
    ".pdf": "DOCS",
    ".md": "DOCS",
    ".jpg": "PHOTOS",
    ".jpeg": "PHOTOS",
    ".png": "PHOTOS",
    ".mp4": "VIDEOS",
    ".mov": "VIDEOS",
    ".zip": "ARCHIVES",
    ".py": "CODE",
    ".js": "CODE",
}


def is_system_file(path: Path) -> bool:
    name = path.name.lower()
    if name in SYSTEM_FILES:
        return True
    if name.endswith(".tmp"):
        return True
    return False


def in_protected_dir(path: Path) -> bool:
    return any(part.lower() in PROTECTED_DIRS for part in path.parents)


# -------------------- Rules parsing --------------------


def rules_to_text(rules: Dict[str, str]) -> str:
    lines = [f"{ext} {cat}" for ext, cat in sorted(rules.items())]
    return "\n".join(lines)


def parse_rules(text: str) -> Tuple[Dict[str, str], List[str]]:
    rules: Dict[str, str] = {}
    invalid: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            invalid.append(raw)
            continue
        ext, cat = parts
        ext = ext.lower()
        if not ext.startswith("."):
            ext = "." + ext
        rules[ext] = cat.upper()
    if not rules:
        rules = dict(DEFAULT_RULES)
    return rules, invalid


# -------------------- Planning --------------------


def iter_files(source_root: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(source_root):
        root_path = Path(root)
        # prune protected dirs
        dirs[:] = [d for d in dirs if d.lower() not in PROTECTED_DIRS]
        for name in files:
            p = root_path / name
            if in_protected_dir(p) or is_system_file(p):
                continue
            yield p


def compute_dest_path(dest_root: Path, source_root: Path, src: Path,
                      category: str, mode: str) -> Path:
    rel = src.relative_to(source_root)
    if mode == "mirror":
        return dest_root / source_root.name / rel
    if mode == "foldersort":
        return dest_root / source_root.name / rel.parent / category / rel.name
    # default: category/source_root/rel
    return dest_root / category / source_root.name / rel


def ensure_unique_path(base: Path, used: set[str]) -> Path:
    candidate = base
    stem = base.stem
    suffix = base.suffix
    counter = 1

    def key(p: Path) -> str:
        return str(p).casefold()

    while True:
        k = key(candidate)
        if k not in used and not candidate.exists():
            used.add(k)
            return candidate
        candidate = base.with_name(f"{stem}_{counter}{suffix}")
        counter += 1


class OperationCancelled(RuntimeError):
    pass


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> Optional[str]:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def build_plan(sources: List[Path], destination: Path, rules_text: str,
               include_duplicates: bool, organize_mode: str = "category",
               progress_cb: Optional[Callable[[int, Optional[int]], None]] = None,
               cancel_event: Optional[threading.Event] = None) -> Tuple[Plan, List[str]]:
    rules, invalid = parse_rules(rules_text)
    plan = Plan()

    # gather stats by size first
    size_map: Dict[int, List[Tuple[Path, Path, os.stat_result]]] = {}
    total_files = 0
    for src_root in sources:
        for fp in iter_files(src_root):
            try:
                st = fp.stat()
            except Exception:
                plan.ignored_files += 1
                continue
            size_map.setdefault(int(st.st_size), []).append((src_root, fp, st))
            total_files += 1

    if progress_cb:
        progress_cb(0, total_files)

    used_destinations: set[str] = set()
    seen = 0
    hash_map: Dict[str, List[Tuple[Path, Path, os.stat_result]]] = {}

    for size, items in size_map.items():
        if cancel_event and cancel_event.is_set():
            raise OperationCancelled("Analysis cancelled")

        # hash even singletons to support duplicate review
        for src_root, fp, st in items:
            if cancel_event and cancel_event.is_set():
                raise OperationCancelled("Analysis cancelled")
            digest = sha256_file(fp)
            if digest is None:
                plan.hash_failures += 1
                plan.ignored_files += 1
                continue
            hash_map.setdefault(digest, []).append((src_root, fp, st))
            seen += 1
            if progress_cb:
                progress_cb(seen, total_files)

    for digest, items in hash_map.items():
        is_duplicate_set = len(items) > 1
        if is_duplicate_set:
            plan.duplicates[digest] = [fp for _, fp, _ in items]

        for src_root, fp, st in items:
            if is_duplicate_set and not include_duplicates:
                plan.ignored_files += 1
                continue

            suffix = fp.suffix.lower() or ".noext"
            category = rules.get(suffix, "MISC")
            planned = compute_dest_path(destination, src_root, fp, category, organize_mode)
            final = ensure_unique_path(planned, used_destinations)

            move = MoveItem(
                src=fp,
                planned_dst=planned,
                final_dst=final,
                category=category,
                source_root=src_root,
                relpath=fp.relative_to(src_root),
                size=int(st.st_size),
                mtime=float(st.st_mtime),
                duplicate_group=digest if is_duplicate_set else "",
            )
            plan.moves.append(move)
            plan.category_counts[category] = plan.category_counts.get(category, 0) + 1

    # sort moves for stable previews
    plan.moves.sort(key=lambda m: (m.category, str(m.relpath).lower()))
    return plan, invalid


# -------------------- Duplicate selection --------------------


def apply_duplicate_selection(plan: Plan, keep_map: Dict[str, Path]) -> Plan:
    delete_paths: List[Path] = []
    keep_lookup: Dict[str, Path] = {group: p for group, p in keep_map.items()}

    filtered_moves: List[MoveItem] = []
    for move in plan.moves:
        group = move.duplicate_group
        if not group:
            filtered_moves.append(move)
            continue
        keep_path = keep_lookup.get(group)
        if keep_path is None or move.src == keep_path:
            filtered_moves.append(move)
        else:
            delete_paths.append(move.src)

    plan.moves = filtered_moves
    plan.duplicate_deletes = delete_paths
    return plan


# -------------------- Execution & undo --------------------


def execute_plan(plan: Plan, dry_run: bool,
                 cancel_event: Optional[threading.Event] = None,
                 max_moves: Optional[int] = None) -> Tuple[Dict[str, int], Optional[Path]]:
    results = {"moved": 0, "trashed": 0, "skipped": 0, "errors": 0}
    if plan.is_empty:
        return results, None

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "max_moves": max_moves,
        "moves": [],
        "deletes": [],
    }

    for idx, move in enumerate(plan.moves):
        if max_moves is not None and idx >= max_moves:
            results["skipped"] += 1
            continue
        if cancel_event and cancel_event.is_set():
            raise OperationCancelled("Execution cancelled")

        src = move.src
        dst = move.final_dst
        entry = {
            "src": str(src),
            "dst": str(dst),
            "category": move.category,
            "source_root": str(move.source_root),
            "relative_path": str(move.relpath),
            "size": move.size,
            "mtime": move.mtime,
        }
        try:
            if dry_run:
                results["moved"] += 1
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                safe_dst = ensure_unique_path(dst, set())
                shutil.move(str(src), str(safe_dst))
                entry["dst"] = str(safe_dst)
                results["moved"] += 1
            manifest["moves"].append(entry)
        except Exception:
            results["errors"] += 1
            entry["error"] = True
            manifest["moves"].append(entry)

    for doomed in plan.duplicate_deletes:
        if cancel_event and cancel_event.is_set():
            raise OperationCancelled("Execution cancelled")
        entry = {"src": str(doomed)}
        try:
            if not doomed.exists():
                results["skipped"] += 1
                entry["missing"] = True
            elif dry_run:
                results["trashed"] += 1
            else:
                doomed.unlink()
                results["trashed"] += 1
            manifest["deletes"].append(entry)
        except Exception:
            results["errors"] += 1
            entry["error"] = True
            manifest["deletes"].append(entry)

    manifest_path: Optional[Path] = None
    if not dry_run:
        undo_dir = Path("undohistory")
        undo_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest_path = undo_dir / f"undo_manifest_{stamp}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return results, manifest_path


def undo_from_manifest(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    restored = 0
    for item in reversed(data.get("moves", [])):
        src = Path(item["dst"])
        dst = Path(item["src"])
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst = ensure_unique_path(dst, set())
        shutil.move(str(src), str(dst))
        restored += 1
    return restored


# -------------------- Simple CLI entrypoint --------------------


def _format_bytes(n: int) -> str:
    value = float(n)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def cli_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Nexus headless engine")
    parser.add_argument("sources", nargs="+", help="Source folders")
    parser.add_argument("--dest", required=True, help="Destination folder")
    parser.add_argument("--rules", help="Rules file (text)")
    parser.add_argument("--include-duplicates", action="store_true")
    parser.add_argument("--mode", choices=["category", "mirror", "foldersort"], default="category")
    parser.add_argument("--execute", action="store_true", help="Execute (otherwise dry run)")

    args = parser.parse_args()

    srcs = [Path(s).expanduser().resolve() for s in args.sources]
    dest = Path(args.dest).expanduser().resolve()

    if args.rules:
        rules_text = Path(args.rules).read_text(encoding="utf-8")
    else:
        rules_text = rules_to_text(DEFAULT_RULES)

    print("[nexus] Building plan...")

    def progress(cur: int, total: Optional[int]) -> None:
        if total:
            print(f"  scanned {cur}/{total} files", end="\r", flush=True)

    plan, invalid = build_plan(srcs, dest, rules_text, args.include_duplicates, args.mode, progress_cb=progress)
    print()  # newline

    if invalid:
        print("[nexus] Invalid rule lines:")
        for line in invalid:
            print("  ", line)

    print(f"[nexus] Planned moves: {len(plan.moves)}")
    print(f"[nexus] Duplicate sets: {len(plan.duplicates)}")
    print(f"[nexus] Ignored files: {plan.ignored_files}")
    total_bytes = sum(m.size for m in plan.moves)
    print(f"[nexus] Total bytes: {_format_bytes(total_bytes)}")

    if not args.execute:
        print("[nexus] Dry run only. Re-run with --execute to apply.")
        return

    print("[nexus] Executing plan...")
    results, manifest_path = execute_plan(plan, dry_run=False)
    print(f"[nexus] Moved: {results['moved']}  Trashed: {results['trashed']}  Errors: {results['errors']}")
    if manifest_path:
        print(f"[nexus] Undo manifest written to: {manifest_path}")


if __name__ == "__main__":  # pragma: no cover
    cli_main()

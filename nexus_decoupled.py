"""
NEXUS File Organizer v2 (Merged)

Goal
- Reliability + safety of the rebuild (plan → execute → undo manifest).
- Attractive, visible UI inspired by the legacy app (dark theme, stat cards, better log).

Notes
- Non-destructive by default via Dry Run.
- Destination safety: blocks drive roots and destinations inside selected sources.
- Preserves per-source relative structure under per-category folders:
    <DEST>/<CATEGORY>/<SOURCE_ROOT_NAME>/<relative/path/to/file>
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
import tempfile
from argparse import ArgumentParser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable

try:
    from send2trash import send2trash
except Exception:
    send2trash = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False


APP_NAME = "NEXUS File Organizer Robust"
APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "nexus_config_robust.json"
UNDO_DIR = APP_DIR / "undo_history"
UNDO_DIR.mkdir(exist_ok=True)

CLOUD_ROOT_NAMES = {
    "onedrive": "OneDrive",
    "dropbox": "Dropbox",
    "iclouddrive": "iCloudDrive",
    "icloudphotos": "iCloudPhotos",
    "google drive": "Google Drive",
    "googledrive": "Google Drive",
}

PROTECTED_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
}

SYSTEM_FILES = {
    "thumbs.db",
    "desktop.ini",
    "ntuser.dat",
    "ntuser.ini",
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    ".ds_store",
    ".localized",
    ".spotlight-v100",
    ".trashes",
    ".fseventsd",
    ".temporaryitems",
    ".volumeicon.icns",
    ".directory",
    ".hidden",
    "lost+found",
    ".nomedia",
    "autorun.inf",
    "recycle.bin",
    "$recycle.bin",
}
SYSTEM_PREFIXES = ("~$",)
SYSTEM_SUFFIXES = (".tmp", ".temp", ".crdownload", ".part", ".lock")


DEFAULT_RULES = {
    ".txt": "DOCS",
    ".md": "DOCS",
    ".pdf": "DOCS",
    ".doc": "DOCS",
    ".docx": "DOCS",
    ".rtf": "DOCS",
    ".odt": "DOCS",
    ".xls": "SHEETS",
    ".xlsx": "SHEETS",
    ".csv": "SHEETS",
    ".ppt": "SLIDES",
    ".pptx": "SLIDES",
    ".jpg": "PHOTOS",
    ".jpeg": "PHOTOS",
    ".png": "PHOTOS",
    ".gif": "PHOTOS",
    ".bmp": "PHOTOS",
    ".webp": "PHOTOS",
    ".svg": "PHOTOS",
    ".heic": "PHOTOS",
    ".mp3": "AUDIO",
    ".wav": "AUDIO",
    ".flac": "AUDIO",
    ".m4a": "AUDIO",
    ".aac": "AUDIO",
    ".opus": "AUDIO",
    ".mp4": "VIDEOS",
    ".mkv": "VIDEOS",
    ".avi": "VIDEOS",
    ".mov": "VIDEOS",
    ".zip": "ARCHIVES",
    ".7z": "ARCHIVES",
    ".rar": "ARCHIVES",
    ".tar": "ARCHIVES",
    ".gz": "ARCHIVES",
    ".py": "CODE",
    ".js": "CODE",
    ".ts": "CODE",
    ".tsx": "CODE",
    ".jsx": "CODE",
    ".java": "CODE",
    ".cs": "CODE",
    ".cpp": "CODE",
    ".c": "CODE",
    ".h": "CODE",
    ".hpp": "CODE",
    ".json": "CODE",
    ".yaml": "CODE",
    ".yml": "CODE",
    ".xml": "CODE",
    ".html": "CODE",
    ".css": "CODE",
    ".ps1": "CODE",
    ".sh": "CODE",
    ".bat": "CODE",
    ".exe": "APPS",
    ".msi": "APPS",
}

CATEGORY_COLORS = {
    "PHOTOS": "#ec4899",
    "VIDEOS": "#f59e0b",
    "DOCS": "#3b82f6",
    "SHEETS": "#10b981",
    "SLIDES": "#f97316",
    "AUDIO": "#8b5cf6",
    "ARCHIVES": "#ef4444",
    "CODE": "#00d9ff",
    "APPS": "#6366f1",
    "FONTS": "#a78bfa",
    "MISC": "#64748b",
}

FILE_ICONS = {
    ".jpg": "IMG",
    ".jpeg": "IMG",
    ".png": "IMG",
    ".gif": "IMG",
    ".webp": "IMG",
    ".bmp": "IMG",
    ".heic": "IMG",
    ".mp4": "VID",
    ".mov": "VID",
    ".mkv": "VID",
    ".avi": "VID",
    ".mp3": "AUD",
    ".wav": "AUD",
    ".flac": "AUD",
    ".m4a": "AUD",
    ".pdf": "PDF",
    ".doc": "DOC",
    ".docx": "DOC",
    ".txt": "TXT",
    ".zip": "ZIP",
    ".rar": "ZIP",
    ".7z": "ZIP",
    ".py": "PY",
    ".js": "JS",
    ".ts": "TS",
    ".json": "CFG",
}


class Theme:
    BG_DEEP = "#08111f"
    BG_DARK = "#0f1b2d"
    BG_CARD = "#132238"
    BG_HOVER = "#1b2f4a"
    BG_SIDEBAR = "#0b1526"
    BG_PANEL = "#102033"
    BORDER = "#1d3856"
    BORDER_SOFT = "#2b4a6d"

    TEXT_PRIMARY = "#f4f7fb"
    TEXT_SECONDARY = "#a9bfd6"
    TEXT_MUTED = "#5f7894"
    TEXT_GLOW = "#ebf5ff"

    CYAN = "#52d8ff"
    PURPLE = "#8b7cff"
    INDIGO = "#5f83ff"
    PINK = "#ff7aa2"
    GOLD = "#ffc857"
    TEAL = "#53e0c1"
    PANEL_ALT = "#0b1727"
    PANEL_RAISED = "#17304b"

    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    ERROR = "#ef4444"

    FONT_TITLE = ("Segoe UI Semibold", 20)
    FONT_H2 = ("Segoe UI Semibold", 13)
    FONT_H3 = ("Segoe UI Semibold", 11)
    FONT_BODY = ("Segoe UI", 10)
    FONT_SMALL = ("Segoe UI", 9)
    FONT_MONO = ("Consolas", 9)
    FONT_MONO_S = ("Consolas", 8)

    S1 = 4
    S2 = 8
    S3 = 16
    S4 = 24
    S5 = 32


class Pill(tk.Frame):
    def __init__(self, parent, text: str, accent: str, **kwargs):
        super().__init__(parent, bg=Theme.BG_PANEL, highlightbackground=accent, highlightthickness=1, **kwargs)
        self._label = tk.Label(
            self,
            text=text,
            bg=Theme.BG_PANEL,
            fg=accent,
            font=Theme.FONT_SMALL,
            padx=12,
            pady=5,
        )
        self._label.pack()
        self._accent = accent

    def set_text(self, text: str) -> None:
        self._label.config(text=text)

    def set_accent(self, accent: str) -> None:
        self.configure(highlightbackground=accent)
        self._label.config(bg=Theme.BG_PANEL, fg=accent)
        self._accent = accent


class SplashScreen(tk.Toplevel):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=Theme.BG_DEEP)
        self.geometry("620x320")
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = int((sw - 620) / 2)
        y = int((sh - 320) / 2)
        self.geometry(f"620x320+{x}+{y}")

        shell = tk.Frame(self, bg=Theme.BG_PANEL, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        shell.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        glow = tk.Canvas(shell, bg=Theme.BG_PANEL, highlightthickness=0, height=110)
        glow.pack(fill=tk.X)
        glow.create_oval(390, -40, 610, 150, fill=Theme.PURPLE, outline="")
        glow.create_oval(300, -60, 520, 120, fill=Theme.CYAN, outline="")

        tk.Label(shell, text="NEXUS", bg=Theme.BG_PANEL, fg=Theme.CYAN, font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=28)
        tk.Label(shell, text="Robust Command Deck", bg=Theme.BG_PANEL, fg=Theme.TEXT_GLOW, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=28, pady=(6, 0))
        tk.Label(
            shell,
            text="Preparing planner, safeguards, duplicate controls, and execution surfaces.",
            bg=Theme.BG_PANEL,
            fg=Theme.TEXT_SECONDARY,
            font=Theme.FONT_BODY,
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=28, pady=(12, 20))

        self._bar = ttk.Progressbar(shell, mode="indeterminate", length=540)
        self._bar.pack(padx=28, pady=(0, 12))
        self._bar.start(12)
        tk.Label(shell, text="Clinical startup sequence", bg=Theme.BG_PANEL, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", padx=28)

    def close(self) -> None:
        try:
            self._bar.stop()
        except Exception:
            pass
        self.destroy()


@dataclass(slots=True)
class MoveItem:
    src: Path
    planned_dst: Path
    final_dst: Path
    category: str
    source_root: Path
    rel_path: Path
    size: int
    mtime: float
    duplicate_group: str = ""


@dataclass(slots=True)
class Plan:
    moves: list[MoveItem] = field(default_factory=list)
    duplicates: dict[str, list[Path]] = field(default_factory=dict)  # hash -> paths
    duplicate_deletes: list[Path] = field(default_factory=list)
    ignored_files: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    hash_failures: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.moves and not self.duplicate_deletes


@dataclass(slots=True)
class AppState:
    sources: list[str] = field(default_factory=list)
    destination: str = ""
    rules_text: str = ""
    dry_run: bool = True
    include_duplicates: bool = True
    organize_mode: str = "category"
    cloud_safe_mode: bool = True
    batch_limit: int = 500
    last_plan: Plan = field(default_factory=Plan)
    last_manifest: Path | None = None
    status_text: str = ""
    _listeners: dict[str, list[Callable[..., Any]]] = field(default_factory=dict, repr=False)

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        self._listeners.setdefault(event, []).append(callback)

    def emit(self, event: str, *args: Any) -> None:
        for callback in list(self._listeners.get(event, [])):
            try:
                callback(*args)
            except Exception:
                pass

    def update(self, **changes: Any) -> None:
        changed: dict[str, Any] = {}
        for name, value in changes.items():
            if getattr(self, name) != value:
                setattr(self, name, value)
                changed[name] = value
        if not changed:
            return
        for name, value in changed.items():
            self.emit(f"change:{name}", value)
        self.emit("change", changed)

    def set_status(self, text: str) -> None:
        if self.status_text == text:
            return
        self.status_text = text
        self.emit("status", text)


STATE = AppState()


def rules_to_text(rules: dict[str, str]) -> str:
    return "\n".join(f"{ext}={cat}" for ext, cat in sorted(rules.items()))


def parse_rules(text: str) -> tuple[dict[str, str], list[str]]:
    """
    Supports BOTH formats (merged UX):
    - .ext=CATEGORY  (rebuild style)
    - CATEGORY: ext1, ext2, ext3  (legacy style)
    Returns (rules_map, invalid_lines).
    """
    rules: dict[str, str] = {}
    invalid: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if "=" in line:
            ext, cat = line.split("=", 1)
            ext = ext.strip().lower()
            cat = cat.strip().upper().replace(" ", "_")
            if not ext:
                invalid.append(raw)
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            if not cat:
                invalid.append(raw)
                continue
            rules[ext] = cat
            continue

        if ":" in line:
            cat, exts = line.split(":", 1)
            cat = cat.strip().upper().replace(" ", "_")
            if not cat:
                invalid.append(raw)
                continue
            any_added = False
            for e in exts.split(","):
                e = e.strip().lower()
                if not e or e.startswith("#"):
                    continue
                if not e.startswith("."):
                    e = f".{e}"
                rules[e] = cat
                any_added = True
            if not any_added and exts.strip():
                invalid.append(raw)
            continue

        invalid.append(raw)

    if not rules:
        rules = dict(DEFAULT_RULES)
    return rules, invalid


def load_config() -> None:
    if not CONFIG_PATH.exists():
        STATE.rules_text = rules_to_text(DEFAULT_RULES)
        return
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        STATE.sources = [str(Path(p)) for p in data.get("sources", [])]
        STATE.destination = data.get("destination", "")
        STATE.rules_text = data.get("rules_text", rules_to_text(DEFAULT_RULES))
        STATE.dry_run = bool(data.get("dry_run", True))
        STATE.include_duplicates = bool(data.get("include_duplicates", True))
        STATE.organize_mode = str(data.get("organize_mode", "category"))
        STATE.cloud_safe_mode = bool(data.get("cloud_safe_mode", True))
        STATE.batch_limit = max(1, int(data.get("batch_limit", 500)))
    except Exception:
        STATE.rules_text = rules_to_text(DEFAULT_RULES)


def save_config() -> None:
    payload = {
        "sources": STATE.sources,
        "destination": STATE.destination,
        "rules_text": STATE.rules_text,
        "dry_run": STATE.dry_run,
        "include_duplicates": STATE.include_duplicates,
        "organize_mode": STATE.organize_mode,
        "cloud_safe_mode": STATE.cloud_safe_mode,
        "batch_limit": STATE.batch_limit,
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def detect_cloud_root(path: Path) -> tuple[str, Path] | None:
    resolved = path.resolve()
    for part in resolved.parts:
        label = CLOUD_ROOT_NAMES.get(part.lower())
        if label is not None:
            idx = resolved.parts.index(part)
            return label, Path(*resolved.parts[: idx + 1])
    return None


def describe_cloud_context(paths: Iterable[Path]) -> list[str]:
    descriptions: list[str] = []
    seen: set[str] = set()
    for path in paths:
        cloud = detect_cloud_root(path)
        if cloud is None:
            continue
        provider, root = cloud
        key = f"{provider}:{root}"
        if key in seen:
            continue
        seen.add(key)
        descriptions.append(f"{provider} [{root}]")
    return descriptions


def validate_cloud_placement(source_roots: list[Path], dest_root: Path, cloud_safe_mode: bool = True) -> None:
    if not cloud_safe_mode:
        return

    source_clouds = []
    for src in source_roots:
        cloud = detect_cloud_root(src)
        if cloud is not None:
            source_clouds.append(cloud)

    if not source_clouds:
        return

    unique_roots = {str(root).casefold(): (provider, root) for provider, root in source_clouds}
    if len(unique_roots) > 1:
        names = ", ".join(f"{provider} [{root}]" for provider, root in unique_roots.values())
        raise ValueError(
            "Cloud-safe mode blocks planning across multiple cloud roots at once. "
            f"Current sources span: {names}"
        )

    only_provider, only_root = next(iter(unique_roots.values()))
    if not is_under(dest_root, only_root):
        raise ValueError(
            "Cloud-safe mode requires the destination to stay inside the same cloud root as the sources. "
            f"Sources are under {only_provider} [{only_root}], but destination is {dest_root}"
        )


def validate_destination(path: Path, source_roots: Iterable[Path] | None = None) -> Path:
    """
    Safety rules:
    - Block drive roots.
    - Allow destination inside a source root ONLY if it's a subfolder (not equal to the source root).
      If inside, we will exclude it from scanning to avoid recursive ingestion.
    """
    resolved = path.resolve()
    if resolved == Path(resolved.anchor):
        raise ValueError(f"Blocked destination: {resolved} is a drive root")

    if source_roots:
        for src in source_roots:
            src_resolved = src.resolve()
            if resolved == src_resolved:
                raise ValueError(f"Blocked destination: {resolved} cannot be the same as source root {src_resolved}")

    return resolved


def is_system_file(fp: Path) -> bool:
    n = fp.name.lower()
    if n in SYSTEM_FILES:
        return True
    if any(n.startswith(px) for px in SYSTEM_PREFIXES):
        return True
    if any(n.endswith(sx) for sx in SYSTEM_SUFFIXES):
        return True
    return False


def is_in_protected_dir(fp: Path) -> bool:
    # Only check parent dirs, not the filename itself.
    return any(part.lower() in PROTECTED_DIRS for part in fp.parent.parts)


def iter_files(source_root: Path, excluded_roots: Iterable[Path] = ()) -> Iterable[Path]:
    excluded = [Path(ex).resolve() for ex in excluded_roots]

    for root, dirs, files in os.walk(source_root):
        root_path = Path(root).resolve()

        if any(root_path == ex or is_under(root_path, ex) for ex in excluded):
            dirs[:] = []
            continue

        dirs[:] = [d for d in dirs if d.lower() not in PROTECTED_DIRS]

        for name in files:
            path = root_path / name
            if is_in_protected_dir(path):
                continue
            if is_system_file(path):
                continue
            if any(path == ex or is_under(path, ex) for ex in excluded):
                continue
            yield path


def build_excluded_roots(source_roots: list[Path], dest_root: Path) -> list[Path]:
    # If destination is inside any source root, exclude it so scanning doesn't recurse into output.
    excluded: list[Path] = []
    for src in source_roots:
        if is_under(dest_root, src):
            excluded.append(dest_root)
            break
    return excluded


def prepare_roots(sources: list[str], destination: str, cloud_safe_mode: bool = True) -> tuple[list[Path], Path, list[Path]]:
    source_roots = [Path(s).resolve() for s in sources if Path(s).exists()]
    if not source_roots:
        raise ValueError("No valid source folders selected")
    dest_root = validate_destination(Path(destination), source_roots)
    validate_cloud_placement(source_roots, dest_root, cloud_safe_mode=cloud_safe_mode)
    excluded_roots = build_excluded_roots(source_roots, dest_root)
    return source_roots, dest_root, excluded_roots



class OperationCancelled(RuntimeError):
    pass


def find_empty_dirs(root: Path, *, keep_root: bool = True) -> list[Path]:
    root = Path(root)
    empties: list[Path] = []
    for dirpath, _, _ in os.walk(root, topdown=False):
        p = Path(dirpath)
        if keep_root and p.resolve() == root.resolve():
            continue
        try:
            if not any(p.iterdir()):
                empties.append(p)
        except OSError:
            continue
    return empties


def compute_dest_path(dest_root: Path, source_root: Path, src_path: Path, category: str, mode: str) -> Path:
    rel_path = src_path.relative_to(source_root)
    if mode == "mirror":
        return dest_root / source_root.name / rel_path
    if mode == "folder_sort":
        return dest_root / source_root.name / rel_path.parent / category / rel_path.name
    return dest_root / category / source_root.name / rel_path


def refresh_plan_counts(plan: Plan) -> None:
    counts: dict[str, int] = {}
    for move in plan.moves:
        counts[move.category] = counts.get(move.category, 0) + 1
    plan.category_counts = counts


def format_bytes(size: int) -> str:
    value = float(size)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def format_mtime(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "unknown"


def icon_for_path(path: Path) -> str:
    return FILE_ICONS.get(path.suffix.lower(), "FILE")


def apply_duplicate_selection(plan: Plan, keep_map: dict[str, Path]) -> Plan:
    delete_paths: list[Path] = []
    keep_lookup = {group: Path(path) for group, path in keep_map.items()}

    filtered_moves: list[MoveItem] = []
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
    refresh_plan_counts(plan)
    return plan


def build_plan_core(
    source_roots: list[Path],
    dest_root: Path,
    excluded_roots: list[Path],
    rules: dict[str, str],
    include_duplicates: bool,
    organize_mode: str = "category",
    total_files: int | None = None,
    progress_cb=None,
    cancel_event: threading.Event | None = None,
) -> Plan:
    plan = Plan()

    # PERF: group by size first; only hash where size collisions exist.
    # size -> [(source_root, file_path, stat)]
    size_map: dict[int, list[tuple[Path, Path, os.stat_result]]] = {}
    seen = 0
    for source_root in source_roots:
        for file_path in iter_files(source_root, excluded_roots=excluded_roots):
            if cancel_event and cancel_event.is_set():
                raise OperationCancelled("Analysis cancelled")
            try:
                st = file_path.stat()
            except Exception:
                plan.ignored_files += 1
                continue
            size_map.setdefault(int(st.st_size), []).append((source_root, file_path.resolve(), st))
            seen += 1
            if progress_cb and total_files:
                progress_cb(seen, total_files)

    hash_map: dict[str, list[tuple[Path, Path, os.stat_result]]] = {}
    for size, items in size_map.items():
        if size == 0 and len(items) == 1:
            # Single empty file: hashing is cheap but also not necessary.
            # Still hash to keep behavior consistent for duplicates.
            pass

        if len(items) == 1:
            source_root, file_path, st = items[0]
            # Unique size: treat as unique "group" by synthetic key to avoid hashing.
            # This preserves duplicate detection only when it matters (size collisions).
            synthetic = f"__size_unique__:{size}:{file_path}"
            hash_map[synthetic] = [(source_root, file_path, st)]
            continue

        for source_root, file_path, st in items:
            if cancel_event and cancel_event.is_set():
                raise OperationCancelled("Analysis cancelled")
            h = sha256_file(file_path)
            if not h:
                plan.hash_failures += 1
                plan.ignored_files += 1
                continue
            hash_map.setdefault(h, []).append((source_root, file_path, st))

    used_destinations: set[str] = set()

    for group_key, items in hash_map.items():
        is_duplicate_set = not group_key.startswith("__size_unique__") and len(items) > 1
        if is_duplicate_set:
            plan.duplicates[group_key] = [file_path for _, file_path, _ in items]

        for source_root, file_path, st in items:
            if is_duplicate_set and not include_duplicates:
                plan.ignored_files += 1
                continue

            rel_path = file_path.relative_to(source_root)
            suffix = file_path.suffix.lower() or ".no_extension"
            category = rules.get(suffix, "MISC")

            planned = compute_dest_path(dest_root, source_root, file_path, category, organize_mode)
            final = plan_unique_path(planned, used_destinations, existing_check=True)

            move = MoveItem(
                src=file_path,
                planned_dst=planned,
                final_dst=final,
                category=category,
                source_root=source_root,
                rel_path=rel_path,
                size=int(st.st_size),
                mtime=float(st.st_mtime),
                duplicate_group=group_key if is_duplicate_set else "",
            )
            plan.moves.append(move)
            plan.category_counts[category] = plan.category_counts.get(category, 0) + 1

    plan.moves.sort(key=lambda item: (item.category, str(item.rel_path).lower()))
    return plan


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def plan_unique_path(base: Path, used: set[str], existing_check: bool = True) -> Path:
    """
    Ensures uniqueness for preview AND execution determinism.
    - used tracks already planned destinations (casefolded string).
    - existing_check also avoids conflicts with already existing files on disk.
    """
    candidate = base
    counter = 1

    def key(p: Path) -> str:
        return str(p).casefold()

    while True:
        k = key(candidate)
        if k not in used and (not existing_check or not candidate.exists()):
            used.add(k)
            return candidate
        candidate = base.with_name(f"{base.stem}_{counter}{base.suffix}")
        counter += 1


def build_plan(
    sources: list[str],
    destination: str,
    rules_text: str,
    include_duplicates: bool,
    organize_mode: str = "category",
    cloud_safe_mode: bool = True,
) -> tuple[Plan, list[str]]:
    rules, invalid_lines = parse_rules(rules_text)
    source_roots, dest_root, excluded_roots = prepare_roots(sources, destination, cloud_safe_mode=cloud_safe_mode)
    plan = build_plan_core(
        source_roots=source_roots,
        dest_root=dest_root,
        excluded_roots=excluded_roots,
        rules=rules,
        include_duplicates=include_duplicates,
        organize_mode=organize_mode,
        total_files=None,
        progress_cb=None,
    )
    return plan, invalid_lines


def execute_plan(
    plan: Plan,
    dry_run: bool,
    cancel_event: threading.Event | None = None,
    max_moves: int | None = None,
) -> tuple[dict[str, int], Path | None]:
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
            "relative_path": str(move.rel_path),
            "size": move.size,
            "mtime": move.mtime,
        }
        try:
            if dry_run:
                results["moved"] += 1
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                # final_dst was planned to be unique, but still guard at execution time
                # if external changes happened between analyze and execute.
                safe_dst = ensure_unique_path(dst)
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
            elif send2trash is not None:
                send2trash(str(doomed))
                results["trashed"] += 1
            else:
                doomed.unlink()
                results["trashed"] += 1
            manifest["deletes"].append(entry)
        except Exception:
            results["errors"] += 1
            entry["error"] = True
            manifest["deletes"].append(entry)

    manifest_path: Path | None = None
    if not dry_run:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest_path = UNDO_DIR / f"undo_manifest_{stamp}.json"
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
            dst = ensure_unique_path(dst)
        shutil.move(str(src), str(dst))
        restored += 1
    return restored


def parse_dropped_paths(raw_data: str) -> list[str]:
    if not raw_data:
        return []

    parts: list[str] = []
    token: list[str] = []
    brace_depth = 0
    in_quotes = False

    def flush() -> None:
        if token:
            value = "".join(token).strip().strip('"')
            if value:
                parts.append(value)
            token.clear()

    for char in raw_data.strip():
        if char == '"' and brace_depth == 0:
            in_quotes = not in_quotes
            continue
        if char == '{' and not in_quotes:
            if brace_depth > 0:
                token.append(char)
            brace_depth += 1
            continue
        if char == '}' and not in_quotes and brace_depth > 0:
            brace_depth -= 1
            if brace_depth > 0:
                token.append(char)
            else:
                flush()
            continue
        if char.isspace() and brace_depth == 0 and not in_quotes:
            flush()
            continue
        token.append(char)

    flush()
    return parts


class HoverButton(tk.Frame):
    def __init__(self, parent, text: str, command=None, accent: str | None = None, icon: str = "", **kwargs):
        self.command = command
        self._enabled = True
        self.accent = accent or Theme.INDIGO
        super().__init__(parent, bg=Theme.BG_CARD, cursor="hand2", highlightbackground=Theme.BORDER_SOFT, highlightthickness=1, **kwargs)

        self._bg = Theme.BG_CARD
        self._hover_bg = Theme.PANEL_RAISED

        accent_bar = tk.Frame(self, bg=self.accent, width=4, cursor="hand2")
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        body = tk.Frame(self, bg=self._bg, padx=Theme.S3, pady=10, cursor="hand2")
        body.pack(fill=tk.BOTH, expand=True)

        row = tk.Frame(body, bg=self._bg, cursor="hand2")
        row.pack(fill=tk.X)
        if icon:
            icon_box = tk.Label(
                row,
                text=icon,
                width=4,
                bg=Theme.BG_DEEP,
                fg=self.accent,
                font=Theme.FONT_SMALL,
                padx=4,
                pady=4,
                cursor="hand2",
            )
            icon_box.pack(side=tk.LEFT, padx=(0, Theme.S2))
        else:
            icon_box = None

        label = tk.Label(row, text=text, bg=self._bg, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H3, cursor="hand2", anchor="w")
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        sublabel = tk.Label(body, text="Action surface", bg=self._bg, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, cursor="hand2", anchor="w")
        sublabel.pack(fill=tk.X, pady=(4, 0))

        self._parts = tuple(w for w in (self, accent_bar, body, row, icon_box, label, sublabel) if w is not None)

        def on_enter(_=None):
            body.config(bg=self._hover_bg)
            row.config(bg=self._hover_bg)
            label.config(bg=self._hover_bg)
            sublabel.config(bg=self._hover_bg, fg=Theme.TEXT_SECONDARY)

        def on_leave(_=None):
            body.config(bg=self._bg)
            row.config(bg=self._bg)
            label.config(bg=self._bg)
            sublabel.config(bg=self._bg, fg=Theme.TEXT_MUTED)

        def on_click(_=None):
            if self.command and self._enabled:
                self.command()

        for w in self._parts:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

    def set_interactive(self, interactive: bool = True) -> None:
        self._enabled = interactive
        cursor = "hand2" if interactive else "arrow"
        for w in getattr(self, "_parts", (self,)):
            try:
                w.configure(cursor=cursor)
            except Exception:
                pass
        try:
            self.configure(bg=Theme.BG_CARD if interactive else Theme.BG_PANEL)
        except Exception:
            pass


class StatCard(tk.Frame):
    def __init__(self, parent, title: str, value: str, accent: str, **kwargs):
        super().__init__(parent, bg=Theme.BG_PANEL, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1, **kwargs)
        body = tk.Frame(self, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3)
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        top = tk.Frame(body, bg=Theme.BG_PANEL)
        top.pack(fill=tk.X)
        tk.Label(top, text=title.upper(), bg=Theme.BG_PANEL, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(side=tk.LEFT)
        tk.Label(top, text="●", bg=Theme.BG_PANEL, fg=accent, font=Theme.FONT_SMALL).pack(side=tk.RIGHT)
        self._value = tk.Label(body, text=value, bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=("Segoe UI Semibold", 24))
        self._value.pack(anchor="w")
        self._meta = tk.Label(body, text="Awaiting analysis", bg=Theme.BG_PANEL, fg=accent, font=Theme.FONT_SMALL)
        self._meta.pack(anchor="w", pady=(2, 0))

    def set_value(self, value: str) -> None:
        self._value.config(text=value)

    def set_meta(self, value: str) -> None:
        self._meta.config(text=value)


class LogView(tk.Frame):
    COLORS = {"success": Theme.SUCCESS, "error": Theme.ERROR, "warning": Theme.WARNING, "info": Theme.TEXT_SECONDARY}

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=Theme.BG_DARK, **kwargs)
        self._canvas = tk.Canvas(self, bg=Theme.BG_DARK, highlightthickness=0)
        self._scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._inner = tk.Frame(self._canvas, bg=Theme.BG_DARK)
        self._window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_inner_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._window, width=event.width)

    def add(self, message: str, level: str = "info") -> None:
        color = self.COLORS.get(level, Theme.TEXT_SECONDARY)
        row = tk.Frame(self._inner, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER, highlightthickness=1)
        row.pack(fill=tk.X, padx=Theme.S2, pady=3)

        ts = time.strftime("%H:%M:%S")
        tk.Label(row, text=ts, bg=Theme.BG_CARD, fg=Theme.TEXT_MUTED, font=Theme.FONT_MONO_S, width=9, anchor="w").pack(
            side=tk.LEFT
        )
        tk.Label(row, text=("●" if level in ("success", "error", "warning") else "·"), bg=Theme.BG_CARD, fg=color, font=Theme.FONT_MONO_S).pack(
            side=tk.LEFT, padx=4
        )
        tk.Label(row, text=message, bg=Theme.BG_CARD, fg=color, font=Theme.FONT_MONO, anchor="w", justify="left").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self._canvas.yview_moveto(1.0)


class DuplicateReviewer(tk.Toplevel):
    def __init__(self, parent: "NexusApp", plan: Plan):
        super().__init__(parent)
        self.parent = parent
        self.plan = plan
        self.groups = list(plan.duplicates.items())
        self.keep_selection: dict[str, Path] = {group: Path(paths[0]) for group, paths in self.groups}
        self.keep_buttons: dict[tuple[str, str], tk.Button] = {}
        self.title("Review Duplicates")
        self.geometry("980x680")
        self.configure(bg=Theme.BG_DEEP)

        container = tk.Frame(self, bg=Theme.BG_DEEP, padx=Theme.S3, pady=Theme.S3)
        container.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            container,
            text="Choose one file to keep from each duplicate set. The rest will be sent to trash on execution.",
            bg=Theme.BG_DEEP,
            fg=Theme.TEXT_PRIMARY,
            font=Theme.FONT_BODY,
            justify="left",
        ).pack(anchor="w", pady=(0, Theme.S3))

        canvas = tk.Canvas(container, bg=Theme.BG_DARK, highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = tk.Frame(canvas, bg=Theme.BG_DARK)
        canvas_window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(canvas_window, width=e.width))

        if not self.groups:
            tk.Label(body, text="No duplicate sets in the current plan.", bg=Theme.BG_DARK, fg=Theme.TEXT_SECONDARY).pack(anchor="w", padx=Theme.S3, pady=Theme.S3)

        for index, (group_key, paths) in enumerate(self.groups, start=1):
            card = tk.Frame(body, bg=Theme.BG_CARD, padx=Theme.S3, pady=Theme.S3)
            card.pack(fill=tk.X, padx=Theme.S2, pady=Theme.S2)
            tk.Label(card, text=f"Duplicate Set {index} ({len(paths)} files)", bg=Theme.BG_CARD, fg=Theme.WARNING, font=Theme.FONT_H3).pack(anchor="w")
            for path in paths:
                meta = self.parent._get_file_meta(path)
                row = tk.Frame(card, bg=Theme.BG_PANEL, padx=10, pady=8, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
                row.pack(fill=tk.X, anchor="w", pady=4)
                top = tk.Frame(row, bg=Theme.BG_PANEL)
                top.pack(fill=tk.X)
                badge = tk.Label(top, text=icon_for_path(path), bg=Theme.INDIGO, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_SMALL, padx=8, pady=4)
                badge.pack(side=tk.LEFT, anchor="w", pady=(0, 6))
                btn = tk.Button(top, text="Keep", command=lambda g=group_key, p=Path(path): self._set_group_keep(g, p), bg=Theme.BG_HOVER, fg=Theme.TEXT_PRIMARY, relief="flat", padx=10, pady=4)
                btn.pack(side=tk.RIGHT)
                self.keep_buttons[(group_key, str(Path(path)))] = btn
                tk.Label(row, text=path.name, bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H3, anchor="w", justify="left").pack(fill=tk.X, anchor="w")
                tk.Label(row, text=str(path), bg=Theme.BG_PANEL, fg=Theme.TEXT_SECONDARY, font=Theme.FONT_SMALL, anchor="w", justify="left").pack(fill=tk.X, anchor="w")
                tk.Label(row, text=f"{meta['size']} Modified {meta['mtime']}", bg=Theme.BG_PANEL, fg=Theme.TEAL, font=Theme.FONT_SMALL, anchor="w").pack(fill=tk.X, anchor="w", pady=(2, 0))
            self._refresh_group_buttons(group_key)

        actions = tk.Frame(container, bg=Theme.BG_DEEP)
        actions.pack(fill=tk.X, pady=(Theme.S3, 0))
        tk.Button(actions, text="Apply Review", command=self.apply_review, bg=Theme.SUCCESS, fg=Theme.TEXT_PRIMARY, relief="flat").pack(side=tk.LEFT)
        tk.Button(actions, text="Close", command=self.destroy, bg=Theme.BG_HOVER, fg=Theme.TEXT_PRIMARY, relief="flat").pack(side=tk.LEFT, padx=(Theme.S2, 0))

    def _set_group_keep(self, group_key: str, path: Path) -> None:
        self.keep_selection[group_key] = Path(path)
        self._refresh_group_buttons(group_key)

    def _refresh_group_buttons(self, group_key: str) -> None:
        selected = str(self.keep_selection[group_key])
        for (group, path_str), button in self.keep_buttons.items():
            if group != group_key:
                continue
            is_selected = path_str == selected
            button.config(text="Selected" if is_selected else "Keep", bg=Theme.SUCCESS if is_selected else Theme.BG_HOVER, fg=Theme.TEXT_PRIMARY, state=tk.DISABLED if is_selected else tk.NORMAL)

    def apply_review(self) -> None:
        apply_duplicate_selection(self.plan, self.keep_selection)
        self.parent._display_plan(self.plan)
        self.parent._log(f"Duplicate review applied: {len(self.plan.duplicate_deletes)} file(s) marked for trash.", "info")
        self.parent._set_status(f"Duplicate review applied: {len(self.plan.duplicate_deletes)} marked for trash")
        self.destroy()


class NexusApp(TkinterDnD.Tk if HAS_DND else tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.withdraw()
        self.title(APP_NAME)
        self.geometry("1450x900")
        self.minsize(1150, 720)
        self.configure(bg=Theme.BG_DEEP)

        self._splash = SplashScreen(self)
        self._cancel = threading.Event()
        self._busy = False
        self._current_plan = Plan()
        self._last_summary = {"moves": 0, "trashed": 0, "errors": 0, "mode": "idle", "elapsed": 0.0}
        load_config()
        self._build_style()
        self._build_ui()
        self._wire_state_events()
        self._refresh_sources()
        self._refresh_destination()
        self._refresh_rules()
        self._refresh_toggles()
        self._register_dnd()
        self.after(700, self._finish_startup)
        self._set_status("Ready")
        self._log("Application started", "info")

    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "TCombobox",
            fieldbackground=Theme.BG_CARD,
            background=Theme.BG_CARD,
            foreground=Theme.TEXT_PRIMARY,
            arrowcolor=Theme.CYAN,
            bordercolor=Theme.BORDER_SOFT,
            lightcolor=Theme.BORDER_SOFT,
            darkcolor=Theme.BORDER_SOFT,
            insertcolor=Theme.TEXT_PRIMARY,
        )
        style.map("TCombobox", fieldbackground=[("readonly", Theme.BG_CARD)], selectbackground=[("readonly", Theme.BG_CARD)])
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=Theme.BG_DARK,
            background=Theme.CYAN,
            bordercolor=Theme.BORDER_SOFT,
            lightcolor=Theme.CYAN,
            darkcolor=Theme.CYAN,
        )

        style.configure(
            "Nexus.Treeview",
            background=Theme.BG_DARK,
            fieldbackground=Theme.BG_DARK,
            foreground=Theme.TEXT_PRIMARY,
            rowheight=30,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
        )
        style.configure(
            "Nexus.Treeview.Heading",
            background=Theme.BG_PANEL,
            foreground=Theme.TEXT_GLOW,
            relief="flat",
            font=Theme.FONT_SMALL,
        )
        style.map("Nexus.Treeview", background=[("selected", Theme.BG_HOVER)], foreground=[("selected", Theme.TEXT_PRIMARY)])
        for category, color in CATEGORY_COLORS.items():
            style.map(f"{category}.Treeview", background=[("selected", Theme.BG_HOVER)], foreground=[("selected", Theme.TEXT_PRIMARY)])

        style.configure("TScrollbar", background=Theme.BG_DARK, troughcolor=Theme.BG_DARK, bordercolor=Theme.BG_DARK, arrowcolor=Theme.TEXT_SECONDARY)

    def _build_ui(self) -> None:
        container = tk.Frame(self, bg=Theme.BG_DEEP)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        sidebar_shell = tk.Frame(container, bg=Theme.BG_SIDEBAR, highlightbackground=Theme.BORDER, highlightthickness=1)
        sidebar_shell.grid(row=0, column=0, sticky="ns")
        sidebar_shell.rowconfigure(0, weight=1)
        sidebar_shell.columnconfigure(0, weight=1)

        sidebar_canvas = tk.Canvas(sidebar_shell, bg=Theme.BG_SIDEBAR, highlightthickness=0, width=340)
        sidebar_scroll = ttk.Scrollbar(sidebar_shell, orient="vertical", command=sidebar_canvas.yview)
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_scroll.grid(row=0, column=1, sticky="ns")

        sidebar = tk.Frame(sidebar_canvas, bg=Theme.BG_SIDEBAR, padx=Theme.S4, pady=Theme.S4)
        sidebar_window = sidebar_canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", lambda _e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.bind("<Configure>", lambda e: sidebar_canvas.itemconfigure(sidebar_window, width=e.width))

        main = tk.Frame(container, bg=Theme.BG_DEEP, padx=Theme.S4, pady=Theme.S4)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(6, weight=1)
        main.rowconfigure(7, weight=1)

        # Sidebar header
        brand = tk.Frame(sidebar, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        brand.pack(fill=tk.X, pady=(0, Theme.S3))
        tk.Label(brand, text="NEXUS", bg=Theme.BG_PANEL, fg=Theme.CYAN, font=("Segoe UI Semibold", 26)).pack(anchor="w")
        tk.Label(brand, text="Studio-grade file operations for large collections", bg=Theme.BG_PANEL, fg=Theme.TEXT_SECONDARY, font=Theme.FONT_SMALL, wraplength=240, justify="left").pack(anchor="w", pady=(4, 0))

        tk.Label(sidebar, text="Operations", bg=Theme.BG_SIDEBAR, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", pady=(0, Theme.S2))

        HoverButton(sidebar, "Add Source", self.add_source, accent=Theme.INDIGO, icon="+").pack(fill=tk.X, pady=4)
        HoverButton(sidebar, "Remove Source", self.remove_source, accent=Theme.PURPLE, icon="-").pack(fill=tk.X, pady=4)
        HoverButton(sidebar, "Choose Destination", self.choose_destination, accent=Theme.CYAN, icon="DIR").pack(fill=tk.X, pady=(Theme.S2, 4))
        HoverButton(sidebar, "Analyze", self.start_analyze, accent=Theme.CYAN, icon="SCAN").pack(fill=tk.X, pady=(Theme.S4, 4))
        self.execute_button = HoverButton(sidebar, "Execute", self.start_execute, accent=Theme.SUCCESS, icon="RUN")
        self.execute_button.pack(fill=tk.X, pady=4)
        self.review_button = HoverButton(sidebar, "Review Duplicates", self.open_duplicate_reviewer, accent=Theme.WARNING, icon="DUPE")
        self.review_button.pack(fill=tk.X, pady=4)
        HoverButton(sidebar, "Undo Last Run", self.undo_last_run, accent=Theme.WARNING, icon="UNDO").pack(fill=tk.X, pady=(Theme.S2, 4))
        HoverButton(sidebar, "Clear Plan", self.clear_plan, accent=Theme.TEXT_MUTED, icon="CLR").pack(fill=tk.X, pady=(Theme.S2, 0))

        self.cancel_button = tk.Button(sidebar, text="Cancel Current Operation", command=self.cancel_operation, state=tk.DISABLED, bg=Theme.ERROR, fg=Theme.TEXT_PRIMARY, relief="flat", activebackground=Theme.ERROR, activeforeground=Theme.TEXT_PRIMARY, padx=10, pady=10)
        self.cancel_button.pack(fill=tk.X, pady=(Theme.S2, 0))

        toggle_frame = tk.Frame(sidebar, bg=Theme.BG_PANEL, pady=Theme.S3, padx=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        toggle_frame.pack(fill=tk.X)
        tk.Label(toggle_frame, text="Safety Controls", bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H2).pack(anchor="w", pady=(0, Theme.S2))
        self.dry_run_check = ttk.Checkbutton(toggle_frame, text="Dry Run (recommended)", command=self.toggle_dry_run)
        self.dry_run_check.pack(anchor="w", pady=2)
        self.include_dupes_check = ttk.Checkbutton(toggle_frame, text="Include duplicates in moves", command=self.toggle_include_duplicates)
        self.include_dupes_check.pack(anchor="w", pady=2)
        self.cloud_safe_check = ttk.Checkbutton(toggle_frame, text="Cloud-safe mode", command=self.toggle_cloud_safe_mode)
        self.cloud_safe_check.pack(anchor="w", pady=2)
        tk.Label(toggle_frame, text="Organization mode", bg=Theme.BG_PANEL, fg=Theme.TEXT_SECONDARY, font=Theme.FONT_SMALL).pack(anchor="w", pady=(Theme.S2, 2))
        self.mode_menu = ttk.Combobox(toggle_frame, values=("category", "mirror", "folder_sort"), state="readonly")
        self.mode_menu.pack(fill=tk.X)
        self.mode_menu.bind("<<ComboboxSelected>>", lambda _event: self.toggle_organize_mode())
        tk.Label(toggle_frame, text="Live batch limit", bg=Theme.BG_PANEL, fg=Theme.TEXT_SECONDARY, font=Theme.FONT_SMALL).pack(anchor="w", pady=(Theme.S2, 2))
        self.batch_menu = ttk.Combobox(toggle_frame, values=("100", "250", "500", "1000"), state="readonly")
        self.batch_menu.pack(fill=tk.X)
        self.batch_menu.bind("<<ComboboxSelected>>", lambda _event: self.toggle_batch_limit())

        status_shell = tk.Frame(sidebar, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        status_shell.pack(fill=tk.X, pady=(Theme.S3, 0))
        tk.Label(status_shell, text="Status", bg=Theme.BG_PANEL, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
        self.status_label = tk.Label(status_shell, text=STATE.status_text or "Ready", bg=Theme.BG_PANEL, fg=Theme.TEXT_SECONDARY, wraplength=260, justify="left")
        self.status_label.pack(anchor="w", pady=(4, 0))

        # Hero
        hero = tk.Frame(main, bg=Theme.BG_PANEL, padx=Theme.S4, pady=Theme.S4, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        hero.grid(row=0, column=0, sticky="ew")
        hero.columnconfigure(0, weight=1)
        hero.columnconfigure(1, weight=0)

        tk.Frame(hero, bg=Theme.CYAN, height=4).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, Theme.S3))
        glow = tk.Canvas(hero, bg=Theme.BG_PANEL, height=54, highlightthickness=0)
        glow.grid(row=0, column=0, columnspan=2, sticky="ne")
        glow.create_oval(720, -40, 980, 150, fill=Theme.PURPLE, outline="")
        glow.create_oval(560, -60, 850, 110, fill=Theme.CYAN, outline="")
        tk.Label(hero, text="Command Deck", bg=Theme.BG_PANEL, fg=Theme.TEXT_GLOW, font=("Segoe UI Semibold", 30)).grid(row=1, column=0, sticky="w")
        tk.Label(
            hero,
            text="High-visibility planning, deliberate execution, and cloud-aware control in one professional workspace.",
            bg=Theme.BG_PANEL,
            fg=Theme.TEXT_SECONDARY,
            font=Theme.FONT_BODY,
            justify="left",
            wraplength=760,
        ).grid(row=2, column=0, sticky="w", pady=(6, Theme.S3))

        hero_right = tk.Frame(hero, bg=Theme.BG_PANEL)
        hero_right.grid(row=1, column=1, rowspan=2, sticky="ne", padx=(Theme.S3, 0))
        self.pill_dry = Pill(hero_right, "DRY RUN", Theme.GOLD)
        self.pill_dry.pack(anchor="e", pady=3)
        self.pill_mode = Pill(hero_right, "MODE: CATEGORY", Theme.CYAN)
        self.pill_mode.pack(anchor="e", pady=3)
        self.pill_dupes = Pill(hero_right, "DUPES: 0", Theme.PURPLE)
        self.pill_dupes.pack(anchor="e", pady=3)
        self.pill_cloud = Pill(hero_right, "CLOUD SAFE", Theme.TEAL)
        self.pill_cloud.pack(anchor="e", pady=3)

        # Main header + stats
        header = tk.Frame(main, bg=Theme.BG_DEEP)
        header.grid(row=1, column=0, sticky="ew", pady=(Theme.S3, 0))
        tk.Label(header, text="Overview", bg=Theme.BG_DEEP, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_TITLE).pack(side=tk.LEFT)
        header_right = tk.Frame(header, bg=Theme.BG_DEEP)
        header_right.pack(side=tk.RIGHT)
        self.analyze_progress = ttk.Progressbar(header_right, mode="determinate", length=220)
        self.analyze_progress.pack(side=tk.TOP, padx=(Theme.S3, 0), pady=(0, 0))
        self.analyze_progress_label = tk.Label(
            header_right,
            text="No analysis running",
            bg=Theme.BG_DEEP,
            fg=Theme.TEXT_SECONDARY,
            font=Theme.FONT_SMALL,
            anchor="e",
        )
        self.analyze_progress_label.pack(side=tk.TOP, fill=tk.X, padx=(Theme.S3, 0), pady=(2, 0))

        stats = tk.Frame(main, bg=Theme.BG_DEEP)
        stats.grid(row=2, column=0, sticky="ew", pady=(Theme.S3, Theme.S3))
        stats.columnconfigure((0, 1, 2, 3), weight=1, uniform="stats")

        self.card_files = StatCard(stats, "Planned Moves", "—", Theme.CYAN)
        self.card_files.grid(row=0, column=0, sticky="ew", padx=(0, Theme.S2))
        self.card_cats = StatCard(stats, "Categories", "—", Theme.PURPLE)
        self.card_cats.grid(row=0, column=1, sticky="ew", padx=(Theme.S2, Theme.S2))
        self.card_dupes = StatCard(stats, "Duplicate Sets", "—", Theme.WARNING)
        self.card_dupes.grid(row=0, column=2, sticky="ew", padx=(Theme.S2, Theme.S2))
        self.card_ignored = StatCard(stats, "Ignored", "—", Theme.TEXT_MUTED)
        self.card_ignored.grid(row=0, column=3, sticky="ew", padx=(Theme.S2, 0))
        self.card_files.set_meta("Rows ready for execution")
        self.card_cats.set_meta("Distinct output buckets")
        self.card_dupes.set_meta("Review before live move")
        self.card_ignored.set_meta("System or blocked files")

        self.summary_card = tk.Frame(main, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        self.summary_card.grid(row=3, column=0, sticky="ew", pady=(0, Theme.S3))
        self.summary_card.columnconfigure(1, weight=1)
        tk.Frame(self.summary_card, bg=Theme.PINK, width=4).grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, Theme.S3))
        tk.Label(self.summary_card, text="Run Summary", bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H2).grid(row=0, column=1, sticky="w")
        self.summary_label = tk.Label(self.summary_card, text="No execution yet. Analyze a plan, review duplicates, and run when ready.", bg=Theme.BG_PANEL, fg=Theme.TEXT_SECONDARY, font=Theme.FONT_BODY, justify="left", wraplength=1000)
        self.summary_label.grid(row=1, column=1, sticky="w")

        # Sources + destination
        io_row = tk.Frame(main, bg=Theme.BG_DEEP)
        io_row.grid(row=4, column=0, sticky="ew")
        io_row.columnconfigure(0, weight=1)
        io_row.columnconfigure(1, weight=1)

        src_card = tk.Frame(io_row, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        src_card.grid(row=0, column=0, sticky="nsew", padx=(0, Theme.S2))
        tk.Label(src_card, text="Sources", bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H2).pack(anchor="w")
        tk.Label(src_card, text="Files are scanned recursively inside selected sources. Protected folders and system files are skipped automatically.", bg=Theme.BG_PANEL, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, wraplength=420, justify="left").pack(anchor="w", pady=(2, Theme.S2))
        self.sources_list = tk.Listbox(src_card, height=6, bg=Theme.BG_DARK, fg=Theme.TEXT_PRIMARY, selectbackground=Theme.INDIGO, relief="flat", highlightthickness=1, highlightbackground=Theme.BORDER_SOFT)
        self.sources_list.pack(fill=tk.BOTH, expand=True, pady=(Theme.S2, 0))

        dst_card = tk.Frame(io_row, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        dst_card.grid(row=0, column=1, sticky="nsew", padx=(Theme.S2, 0))
        tk.Label(dst_card, text="Destination", bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H2).pack(anchor="w")
        tk.Label(dst_card, text="Final staging area for every planned move.", bg=Theme.BG_PANEL, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", pady=(2, Theme.S2))
        self.destination_label = tk.Label(dst_card, text="", bg=Theme.BG_DARK, fg=Theme.TEXT_PRIMARY, wraplength=520, justify="left", padx=12, pady=12, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        self.destination_label.pack(anchor="w", pady=(Theme.S2, 0))

        # Rules
        rules_card = tk.Frame(main, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        rules_card.grid(row=5, column=0, sticky="ew", pady=(Theme.S3, 0))
        tk.Label(rules_card, text="Classification Rules", bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H2).pack(anchor="w")
        tk.Label(rules_card, text="Supports both `.ext=CATEGORY` and `CATEGORY: ext1, ext2` formats.", bg=Theme.BG_PANEL, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", pady=(2, Theme.S2))
        self.rules_text = tk.Text(rules_card, height=8, bg=Theme.BG_DARK, fg=Theme.TEXT_PRIMARY, insertbackground=Theme.TEXT_PRIMARY, relief="flat", highlightthickness=1, highlightbackground=Theme.BORDER_SOFT)
        self.rules_text.pack(fill=tk.X, expand=False, pady=(Theme.S2, 0))

        # Planned moves table
        table_card = tk.Frame(main, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        table_card.grid(row=6, column=0, sticky="nsew", pady=(Theme.S3, Theme.S2))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(1, weight=1)

        tk.Label(table_card, text="Execution Preview", bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H2).grid(row=0, column=0, sticky="w")
        tk.Label(table_card, text="Preview rows match execution order and resolved destination paths.", bg=Theme.BG_PANEL, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).grid(row=0, column=0, sticky="e")

        columns = ("source", "category", "relative", "destination")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", style="Nexus.Treeview")
        self.tree.heading("source", text="Source Root")
        self.tree.heading("category", text="Category")
        self.tree.heading("relative", text="Relative Path")
        self.tree.heading("destination", text="Final Destination")
        self.tree.column("source", width=170, anchor="w")
        self.tree.column("category", width=120, anchor="w")
        self.tree.column("relative", width=360, anchor="w")
        self.tree.column("destination", width=560, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(Theme.S2, 0))

        yscroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=1, column=1, sticky="ns", padx=(Theme.S2, 0))

        # Log
        log_card = tk.Frame(main, bg=Theme.BG_PANEL, padx=Theme.S3, pady=Theme.S3, highlightbackground=Theme.BORDER_SOFT, highlightthickness=1)
        log_card.grid(row=7, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)
        tk.Label(log_card, text="Operational Log", bg=Theme.BG_PANEL, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_H2).grid(row=0, column=0, sticky="w")
        self.log_view = LogView(log_card)
        self.log_view.grid(row=1, column=0, sticky="nsew", pady=(Theme.S2, 0))
        self._set_action_state(False, False)

    def _wire_state_events(self) -> None:
        STATE.subscribe("status", self._on_state_status)
        STATE.subscribe("change", self._on_state_change)

    def _on_state_status(self, text: str) -> None:
        if hasattr(self, "status_label"):
            self.status_label.config(text=text)

    def _on_state_change(self, _changes: dict[str, Any]) -> None:
        self._sync_hero_state()

    def _set_status(self, text: str) -> None:
        STATE.set_status(text)

    def _finish_startup(self) -> None:
        if hasattr(self, "_splash") and self._splash is not None:
            self._splash.close()
            self._splash = None
        self.deiconify()

    def _log(self, text: str, level: str = "info") -> None:
        self.log_view.add(text, level=level)

    def _register_dnd(self) -> None:
        if not HAS_DND:
            self._log("Drag-and-drop unavailable: install tkinterdnd2 to enable it.", "info")
            return
        self.sources_list.drop_target_register(DND_FILES)
        self.sources_list.dnd_bind("<<Drop>>", self._handle_source_drop)
        self.destination_label.drop_target_register(DND_FILES)
        self.destination_label.dnd_bind("<<Drop>>", self._handle_destination_drop)
        self._log("Drag-and-drop enabled for sources and destination.", "success")

    def _handle_source_drop(self, event) -> None:
        added = 0
        for path_text in parse_dropped_paths(event.data):
            path = Path(path_text)
            if path.is_dir():
                resolved = str(path.resolve())
                if resolved not in STATE.sources:
                    STATE.sources.append(resolved)
                    added += 1
        if added:
            save_config()
            self._refresh_sources()
            self._log(f"Added {added} source folder(s) via drag-and-drop.", "success")

    def _handle_destination_drop(self, event) -> None:
        paths = parse_dropped_paths(event.data)
        if not paths:
            return
        path = Path(paths[0])
        if not path.is_dir():
            return
        try:
            resolved = validate_destination(path, [Path(s) for s in STATE.sources]).resolve()
            validate_cloud_placement([Path(s) for s in STATE.sources if Path(s).exists()], resolved, cloud_safe_mode=STATE.cloud_safe_mode)
        except ValueError as exc:
            self._log(str(exc), "error")
            messagebox.showerror("Invalid Destination", str(exc))
            return
        STATE.update(destination=str(resolved))
        save_config()
        self._refresh_destination()
        self._log(f"Destination set via drag-and-drop: {resolved}", "success")

    def _refresh_sources(self) -> None:
        self.sources_list.delete(0, "end")
        for item in STATE.sources:
            self.sources_list.insert("end", item)

    def _refresh_destination(self) -> None:
        self.destination_label.config(text=STATE.destination or "No destination selected")

    def _refresh_rules(self) -> None:
        self.rules_text.delete("1.0", "end")
        self.rules_text.insert("1.0", STATE.rules_text or rules_to_text(DEFAULT_RULES))

    def _refresh_toggles(self) -> None:
        self.dry_run_check.state(["selected"] if STATE.dry_run else ["!selected"])
        self.include_dupes_check.state(["selected"] if STATE.include_duplicates else ["!selected"])
        self.cloud_safe_check.state(["selected"] if STATE.cloud_safe_mode else ["!selected"])
        self.mode_menu.set(STATE.organize_mode)
        self.batch_menu.set(str(STATE.batch_limit))
        self._sync_hero_state()

    def toggle_dry_run(self) -> None:
        STATE.update(dry_run=self.dry_run_check.instate(["selected"]))
        save_config()
        self._log(f"Dry Run set to {STATE.dry_run}", "info")

    def toggle_include_duplicates(self) -> None:
        STATE.update(include_duplicates=self.include_dupes_check.instate(["selected"]))
        save_config()
        self._log(f"Include duplicates set to {STATE.include_duplicates}", "info")

    def toggle_cloud_safe_mode(self) -> None:
        STATE.update(cloud_safe_mode=self.cloud_safe_check.instate(["selected"]))
        save_config()
        self._log(f"Cloud-safe mode set to {STATE.cloud_safe_mode}", "info")

    def toggle_batch_limit(self) -> None:
        try:
            value = max(1, int(self.batch_menu.get()))
        except ValueError:
            value = 500
            self.batch_menu.set(str(value))
        STATE.update(batch_limit=value)
        save_config()
        self._log(f"Live batch limit set to {STATE.batch_limit}", "info")

    def toggle_organize_mode(self) -> None:
        STATE.update(organize_mode=str(self.mode_menu.get()))
        save_config()
        self._log(f"Organization mode set to {STATE.organize_mode}", "info")

    def _sync_hero_state(self) -> None:
        if not hasattr(self, "pill_dry"):
            return
        if STATE.dry_run:
            self.pill_dry.set_text("DRY RUN")
            self.pill_dry.set_accent(Theme.GOLD)
        else:
            self.pill_dry.set_text("LIVE MOVE")
            self.pill_dry.set_accent(Theme.ERROR)
        self.pill_mode.set_text(f"MODE: {STATE.organize_mode.upper()}")
        dupes = len(STATE.last_plan.duplicates)
        marked = len(STATE.last_plan.duplicate_deletes)
        self.pill_dupes.set_text(f"DUPES: {dupes} / TRASH: {marked}")
        self.pill_dupes.set_accent(Theme.PURPLE if dupes else Theme.TEXT_MUTED)
        if hasattr(self, "pill_cloud"):
            self.pill_cloud.set_text(f"CLOUD SAFE · {STATE.batch_limit}")
            self.pill_cloud.set_accent(Theme.TEAL if STATE.cloud_safe_mode else Theme.TEXT_MUTED)
        self._sync_summary()

    def _set_action_state(self, has_plan: bool, has_duplicates: bool) -> None:
        execute_widget = getattr(self, "execute_button", None)
        if execute_widget is not None:
            execute_widget.command = self.start_execute if has_plan else None
            execute_widget._enabled = has_plan
            if hasattr(execute_widget, "set_interactive"):
                execute_widget.set_interactive(has_plan)

        review_widget = getattr(self, "review_button", None)
        if review_widget is not None:
            review_widget.command = self.open_duplicate_reviewer if has_duplicates else None
            review_widget._enabled = has_duplicates
            if hasattr(review_widget, "set_interactive"):
                review_widget.set_interactive(has_duplicates)

    def _restore_action_handlers(self) -> None:
        if hasattr(self, "execute_button"):
            self.execute_button.command = self.start_execute
        if hasattr(self, "review_button"):
            self.review_button.command = self.open_duplicate_reviewer

    def _sync_summary(self) -> None:
        if not hasattr(self, "summary_label"):
            return
        summary = self._last_summary
        mode = summary["mode"]
        if mode == "idle":
            self.summary_label.config(text="No execution yet. Analyze a plan, review duplicates, and run when ready.")
            return
        if mode == "cancelled":
            self.summary_label.config(text=f"Run cancelled after {summary['elapsed']:.1f}s. Moves completed: {summary['moves']}, duplicates trashed: {summary['trashed']}, errors: {summary['errors']}.")
            return
        label = "Dry run" if mode == "dry_run" else "Live run"
        self.summary_label.config(text=f"{label} finished in {summary['elapsed']:.1f}s. Moves: {summary['moves']}, duplicates trashed: {summary['trashed']}, errors: {summary['errors']}.")

    def _get_file_meta(self, path: Path) -> dict[str, str]:
        try:
            st = path.stat()
            return {"size": format_bytes(int(st.st_size)), "mtime": format_mtime(float(st.st_mtime))}
        except Exception:
            return {"size": "unknown", "mtime": "unknown"}

    def cancel_operation(self) -> None:
        if not self._busy:
            return
        self._cancel.set()
        self.cancel_button.config(state=tk.DISABLED)
        self._set_status("Cancelling current operation...")
        self._log("Cancellation requested", "warning")

    def add_source(self) -> None:
        path = filedialog.askdirectory(title="Select Source Folder")
        if not path:
            return
        resolved = str(Path(path).resolve())
        if resolved not in STATE.sources:
            STATE.sources.append(resolved)
            save_config()
            self._refresh_sources()
            self._log(f"Added source: {resolved}", "success")

    def remove_source(self) -> None:
        selection = self.sources_list.curselection()
        if not selection:
            return
        idx = selection[0]
        removed = STATE.sources.pop(idx)
        save_config()
        self._refresh_sources()
        self._log(f"Removed source: {removed}", "warning")

    def choose_destination(self) -> None:
        path = filedialog.askdirectory(title="Select Destination Folder")
        if not path:
            return
        try:
            resolved = validate_destination(Path(path), [Path(s) for s in STATE.sources])
            validate_cloud_placement([Path(s) for s in STATE.sources if Path(s).exists()], resolved, cloud_safe_mode=STATE.cloud_safe_mode)
        except ValueError as exc:
            messagebox.showerror("Invalid Destination", str(exc))
            self._log(str(exc), "error")
            return
        STATE.update(destination=str(resolved))
        save_config()
        self._refresh_destination()
        self._log(f"Destination set: {resolved}", "success")

    def _collect_rules_text(self) -> str:
        text = self.rules_text.get("1.0", "end").strip()
        return text or rules_to_text(DEFAULT_RULES)

    def start_analyze(self) -> None:
        if self._busy:
            self._log("Another operation is already running.", "warning")
            return
        self._busy = True
        self._cancel.clear()
        self._restore_action_handlers()
        self._set_action_state(False, False)
        self.cancel_button.config(state=tk.NORMAL)

        # Read Tk widget state on the main thread before the worker starts.
        STATE.update(rules_text=self._collect_rules_text())
        save_config()

        # Reset progress bar for determinate tracking.
        if hasattr(self, "analyze_progress"):
            try:
                self.analyze_progress.configure(mode="determinate", maximum=100, value=0)
                if hasattr(self, "analyze_progress_label"):
                    self.analyze_progress_label.config(text="Preparing analysis…")
            except Exception:
                pass
        thread = threading.Thread(target=self._analyze_worker, args=(STATE.rules_text,), daemon=True)
        thread.start()

    def _analyze_worker(self, rules_text: str) -> None:
        self.after(0, lambda: self._set_status("Analyzing..."))
        start = time.time()
        try:
            # Prepare roots once so we can compute a real total for the progress bar.
            rules, invalid = parse_rules(rules_text)
            source_roots, dest_root, excluded_roots = prepare_roots(
                STATE.sources,
                STATE.destination,
                cloud_safe_mode=STATE.cloud_safe_mode,
            )

            cloud_descriptions = describe_cloud_context([*source_roots, dest_root])
            if cloud_descriptions:
                self.after(0, lambda desc=", ".join(cloud_descriptions): self._log(f"Cloud context: {desc}", "info"))

            total_files = 0
            self.after(0, lambda: self._set_status("Analyzing sources..."))
            for src in source_roots:
                for _ in iter_files(src, excluded_roots=excluded_roots):
                    if self._cancel.is_set():
                        raise OperationCancelled("Analysis cancelled")
                    total_files += 1

            def progress_cb(done: int, total: int) -> None:
                self.after(0, lambda d=done, t=total: self._update_analyze_progress(d, t))

            if total_files > 0:
                self.after(0, lambda count=total_files: self._mark_analyze_stage(f"Hashing and planning {count:,} files..."))

            plan = build_plan_core(
                source_roots=source_roots,
                dest_root=dest_root,
                excluded_roots=excluded_roots,
                rules=rules,
                include_duplicates=STATE.include_duplicates,
                organize_mode=STATE.organize_mode,
                total_files=total_files if total_files > 0 else None,
                progress_cb=progress_cb if total_files > 0 else None,
                cancel_event=self._cancel,
            )
            STATE.last_plan = plan
            self._current_plan = plan
            elapsed = time.time() - start
            self.after(0, lambda: self._display_plan(plan))
            msg = f"Analysis complete: {len(plan.moves)} planned moves in {elapsed:.1f}s"
            self.after(0, lambda: self._set_status(msg))
            self.after(0, lambda: self._log(msg, "success"))
            self.after(0, lambda p=plan: self._after_plan_ready(p))
            if invalid:
                self.after(0, lambda: self._log(f"Rules: {len(invalid)} line(s) ignored (format issues).", "warning"))
        except OperationCancelled as exc:
            self.after(0, lambda: self._set_status(str(exc)))
            self.after(0, lambda: self._log(str(exc), "warning"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Analysis Error", str(exc)))
            self.after(0, lambda: self._set_status("Analysis failed"))
            self.after(0, lambda: self._log(f"Analysis failed: {exc}", "error"))
        finally:
            self._busy = False
            self.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))
            self.after(0, lambda: self._safe_stop_progress())

    def _update_analyze_progress(self, done: int, total: int) -> None:
        if not hasattr(self, "analyze_progress") or total <= 0:
            return
        try:
            self.analyze_progress.configure(mode="determinate", maximum=total)
            self.analyze_progress["value"] = done
            if hasattr(self, "analyze_progress_label"):
                pct = int(done * 100 / total) if total else 0
                self.analyze_progress_label.config(
                    text=f"Analyzing… {done:,} / {total:,} files ({pct}%)"
                )
        except Exception:
            pass

    def _mark_analyze_stage(self, text: str) -> None:
        if hasattr(self, "analyze_progress_label"):
            self.analyze_progress_label.config(text=text)
        self._set_status(text)

    def _safe_stop_progress(self) -> None:
        if hasattr(self, "analyze_progress"):
            try:
                # For determinate bars, just ensure it's full at the end.
                self.analyze_progress["value"] = self.analyze_progress["maximum"]
                if hasattr(self, "analyze_progress_label"):
                    self.analyze_progress_label.config(text="Analysis complete")
            except Exception:
                pass

    def _display_plan(self, plan: Plan) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Avoid freezing the UI for very large plans: cap the preview.
        preview_cap = 25000
        for move in plan.moves[:preview_cap]:
            tag = move.category if move.category in CATEGORY_COLORS else "MISC"
            self.tree.insert(
                "",
                "end",
                values=(move.source_root.name, move.category, str(move.rel_path), str(move.final_dst)),
                tags=(tag,),
            )
        if len(plan.moves) > preview_cap:
            self._log(f"Preview capped at {preview_cap} rows (plan contains {len(plan.moves)}).", "warning")

        for category, color in CATEGORY_COLORS.items():
            self.tree.tag_configure(category, background=Theme.BG_CARD, foreground=color)

        self.card_files.set_value(str(len(plan.moves)))
        self.card_cats.set_value(str(len(plan.category_counts)))
        dupes_label = str(len(plan.duplicates))
        if plan.duplicate_deletes:
            dupes_label = f"{dupes_label} ({len(plan.duplicate_deletes)} trash)"
        self.card_dupes.set_value(dupes_label)
        self.card_ignored.set_value(str(plan.ignored_files))
        self._sync_hero_state()

        if plan.hash_failures:
            self._log(f"Hash failures: {plan.hash_failures} file(s) could not be hashed.", "warning")

    def _after_plan_ready(self, plan: Plan) -> None:
        has_plan = not plan.is_empty
        has_duplicates = bool(plan.duplicates)
        self._set_action_state(has_plan, has_duplicates)
        if has_plan:
            self._log("Plan is loaded. Execute is now available.", "success")
        else:
            self._log(
                "Analysis finished but produced 0 movable files. Execute remains disabled because there is no runnable plan.",
                "warning",
            )
            messagebox.showinfo(
                "No Runnable Plan",
                "Analysis completed, but no movable files were found.\n\nCheck the Planned Moves card and Ignored count.",
            )

    def clear_plan(self) -> None:
        """Reset the current analysis so you can start a fresh set."""
        STATE.last_plan = Plan()
        self._current_plan = STATE.last_plan
        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)
        # Reset stat cards
        self.card_files.set_value("0")
        self.card_cats.set_value("0")
        self.card_dupes.set_value("0")
        self.card_ignored.set_value("0")
        # Reset progress label
        if hasattr(self, "analyze_progress"):
            try:
                self.analyze_progress["value"] = 0
            except Exception:
                pass
        if hasattr(self, "analyze_progress_label"):
            self.analyze_progress_label.config(text="Plan cleared")
        self._set_status("Plan cleared — ready for new analysis")
        self._log("Plan cleared by user", "info")
        self._set_action_state(False, False)
        self._sync_hero_state()

    def open_duplicate_reviewer(self) -> None:
        plan = self._current_plan if not self._current_plan.is_empty or self._current_plan.duplicates else STATE.last_plan
        if not plan.duplicates:
            messagebox.showinfo("Duplicates", "No duplicate sets in the current plan.")
            return
        DuplicateReviewer(self, plan)

    def start_execute(self) -> None:
        if self._busy:
            self._log("Another operation is already running.", "warning")
            return
        plan = self._current_plan if not self._current_plan.is_empty or self._current_plan.duplicate_deletes else STATE.last_plan
        if plan.is_empty:
            self._log("Execute was requested, but no runnable plan is currently loaded.", "warning")
            messagebox.showinfo("Nothing to Do", "No moves in the current plan. Run Analyze first.")
            return

        if not STATE.dry_run:
            confirm = messagebox.askyesno("Confirm Execute", f"Execute {len(plan.moves)} planned moves?")
            if not confirm:
                return

        self._current_plan = plan
        self._busy = True
        self._cancel.clear()
        self.cancel_button.config(state=tk.NORMAL)
        thread = threading.Thread(target=self._execute_worker, daemon=True)
        thread.start()

    def _execute_worker(self) -> None:
        self.after(0, lambda: self._set_status("Executing..."))
        start = time.time()
        try:
            max_moves = None if STATE.dry_run else STATE.batch_limit
            results, manifest = execute_plan(
                self._current_plan,
                STATE.dry_run,
                cancel_event=self._cancel,
                max_moves=max_moves,
            )
            STATE.last_manifest = manifest
            elapsed = time.time() - start

            moved = results["moved"]
            trashed = results["trashed"]
            errors = results["errors"]
            limited = ""
            if max_moves is not None and len(self._current_plan.moves) > max_moves:
                limited = f", batch_limit={max_moves}, remaining={len(self._current_plan.moves) - max_moves}"
            msg = f"Execution complete: moved={moved}, trashed={trashed}, errors={errors}{limited} in {elapsed:.1f}s"
            self._last_summary = {
                "moves": moved,
                "trashed": trashed,
                "errors": errors,
                "mode": "dry_run" if STATE.dry_run else "live",
                "elapsed": elapsed,
            }
            self.after(0, lambda: self._set_status(msg))
            self.after(0, lambda: self._log(msg, "success" if errors == 0 else "warning"))
            if manifest:
                self.after(0, lambda: self._log(f"Undo manifest saved: {manifest}", "info"))

            if not STATE.dry_run:
                empty_dirs: list[Path] = []
                for source in STATE.sources:
                    empty_dirs.extend(find_empty_dirs(Path(source), keep_root=True))
                if empty_dirs:
                    self.after(0, lambda count=len(empty_dirs): self._log(f"Empty folders detected after execution: {count}", "warning"))

            if STATE.dry_run:
                self.after(0, lambda: messagebox.showinfo("Dry Run", f"Would move {moved} items.\nWould trash {trashed} duplicates.\nErrors: {errors}"))
            else:
                self.after(0, lambda: messagebox.showinfo("Complete", f"Moved {moved} items.\nTrashed {trashed} duplicates.\nErrors: {errors}"))
        except OperationCancelled as exc:
            elapsed = time.time() - start
            self._last_summary = {
                "moves": 0,
                "trashed": 0,
                "errors": 0,
                "mode": "cancelled",
                "elapsed": elapsed,
            }
            self.after(0, lambda: self._set_status(str(exc)))
            self.after(0, lambda: self._log(str(exc), "warning"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Execution Error", str(exc)))
            self.after(0, lambda: self._set_status("Execution failed"))
            self.after(0, lambda: self._log(f"Execution failed: {exc}", "error"))
        finally:
            self._busy = False
            self.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))

    def undo_last_run(self) -> None:
        manifest = STATE.last_manifest
        if manifest is None or not manifest.exists():
            json_files = sorted(UNDO_DIR.glob("undo_manifest_*.json"), reverse=True)
            manifest = json_files[0] if json_files else None

        if manifest is None:
            messagebox.showinfo("Undo", "No undo manifest available.")
            return

        confirm = messagebox.askyesno("Undo", f"Restore files from:\n{manifest.name}?")
        if not confirm:
            return

        try:
            restored = undo_from_manifest(manifest)
            self._log(f"Undo restored {restored} item(s) from {manifest.name}", "success")
            self._set_status(f"Undo complete: {restored} restored")
            messagebox.showinfo("Undo Complete", f"Restored {restored} items.")
        except Exception as exc:
            messagebox.showerror("Undo Error", str(exc))
            self._log(f"Undo failed: {exc}", "error")


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="nexus_organizer_test_") as tmp:
        root = Path(tmp)
        src_a = root / "src_a"
        src_b = root / "src_b"
        dest = root / "dest"
        src_a.mkdir()
        src_b.mkdir()
        dest.mkdir()

        (src_a / "photo.jpg").write_bytes(b"photo")
        (src_a / "notes.txt").write_text("note", encoding="utf-8")
        (src_b / "copy1.txt").write_text("same", encoding="utf-8")
        (src_b / "copy2.txt").write_text("same", encoding="utf-8")
        (src_b / "nested").mkdir()
        (src_b / "nested" / "script.py").write_text("print('ok')", encoding="utf-8")

        plan, invalid = build_plan(
            sources=[str(src_a), str(src_b)],
            destination=str(dest),
            rules_text=rules_to_text(DEFAULT_RULES),
            include_duplicates=True,
            organize_mode="category",
            cloud_safe_mode=True,
        )
        assert not invalid
        assert len(plan.moves) == 5
        assert len(plan.duplicates) == 1

        group, paths = next(iter(plan.duplicates.items()))
        keep = sorted(paths)[0]
        apply_duplicate_selection(plan, {group: keep})
        assert len(plan.moves) == 4
        assert len(plan.duplicate_deletes) == 1

        results, manifest = execute_plan(plan, dry_run=True)
        assert manifest is None
        assert results["moved"] == 4
        assert results["trashed"] == 1
        print("SELF-TEST PASSED")
        print(f"moves={results['moved']} trashed={results['trashed']} duplicates={len(plan.duplicates)}")
    return 0


if __name__ == "__main__":
    parser = ArgumentParser(description=APP_NAME)
    parser.add_argument("--self-test", action="store_true", help="Run a non-GUI planning self-test and exit.")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(run_self_test())

    app = NexusApp()
    app.mainloop()

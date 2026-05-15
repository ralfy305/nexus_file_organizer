{
  "app": {
    "name": "NEXUS File Organizer Robust",
    "version": "2.0",
    "config_file": "nexus_config_robust.json",
    "undo_dir": "undo_history"
  },
  "defaults": {
    "dry_run": true,
    "include_duplicates": true,
    "organize_mode": "category",
    "cloud_safe_mode": true,
    "batch_limit": 500,
    "organize_modes": [
      "category",
      "mirror",
      "folder_sort"
    ],
    "batch_limit_options": [
      100,
      250,
      500,
      1000
    ]
  },
  "cloud_root_names": {
    "onedrive": "OneDrive",
    "dropbox": "Dropbox",
    "iclouddrive": "iCloudDrive",
    "icloudphotos": "iCloudPhotos",
    "google drive": "Google Drive",
    "googledrive": "Google Drive"
  },
  "protected_dirs": [
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
    ".mypy_cache"
  ],
  "system_files": [
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
    "$recycle.bin"
  ],
  "system_prefixes": [
    "~$"
  ],
  "system_suffixes": [
    ".tmp",
    ".temp",
    ".crdownload",
    ".part",
    ".lock"
  ],
  "default_rules": {
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
    ".msi": "APPS"
  },
  "category_colors": {
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
    "MISC": "#64748b"
  },
  "file_icons": {
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
    ".json": "CFG"
  },
  "theme": {
    "colors": {
      "BG_DEEP": "#08111f",
      "BG_DARK": "#0f1b2d",
      "BG_CARD": "#132238",
      "BG_HOVER": "#1b2f4a",
      "BG_SIDEBAR": "#0b1526",
      "BG_PANEL": "#102033",
      "BORDER": "#1d3856",
      "BORDER_SOFT": "#2b4a6d",
      "TEXT_PRIMARY": "#f4f7fb",
      "TEXT_SECONDARY": "#a9bfd6",
      "TEXT_MUTED": "#5f7894",
      "TEXT_GLOW": "#ebf5ff",
      "CYAN": "#52d8ff",
      "PURPLE": "#8b7cff",
      "INDIGO": "#5f83ff",
      "PINK": "#ff7aa2",
      "GOLD": "#ffc857",
      "TEAL": "#53e0c1",
      "PANEL_ALT": "#0b1727",
      "PANEL_RAISED": "#17304b",
      "SUCCESS": "#10b981",
      "WARNING": "#f59e0b",
      "ERROR": "#ef4444"
    },
    "fonts": {
      "FONT_TITLE": [
        "Segoe UI Semibold",
        20
      ],
      "FONT_H2": [
        "Segoe UI Semibold",
        13
      ],
      "FONT_H3": [
        "Segoe UI Semibold",
        11
      ],
      "FONT_BODY": [
        "Segoe UI",
        10
      ],
      "FONT_SMALL": [
        "Segoe UI",
        9
      ],
      "FONT_MONO": [
        "Consolas",
        9
      ],
      "FONT_MONO_S": [
        "Consolas",
        8
      ]
    },
    "spacing": {
      "S1": 4,
      "S2": 8,
      "S3": 16,
      "S4": 24,
      "S5": 32
    }
  },
  "ui": {
    "window": {
      "width": 1450,
      "height": 900,
      "min_width": 1150,
      "min_height": 720
    },
    "splash": {
      "width": 620,
      "height": 320
    },
    "plan_preview_cap": 25000,
    "sidebar_width": 340
  }
}
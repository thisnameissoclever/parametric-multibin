"""Resolve machine-specific paths for the analysis tools.

The reference STLs are MultiBuild's original files. Their license forbids
redistributing them, so they are never committed, and each machine states
where its own copies live.

Every setting resolves in this order:
  1. an environment variable,
  2. local-paths.json at the repository root (gitignored; copy
     local-paths.example.json to start one),
  3. a default, where a sensible one exists.

Generated meshes go under .local-build/out/ at the repository root, which is
gitignored and safe to delete.
"""

import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCAL_CONFIG = REPO / "local-paths.json"
BUILD = REPO / ".local-build"

_WINDOWS_OPENSCAD = Path(r"C:\Program Files\OpenSCAD\openscad.exe")


def _local():
    if LOCAL_CONFIG.is_file():
        return json.loads(LOCAL_CONFIG.read_text(encoding="utf-8"))
    return {}


def _openscad():
    found = os.environ.get("OPENSCAD") or _local().get("openscad")
    if found:
        return str(found)
    on_path = shutil.which("openscad")
    if on_path:
        return on_path
    if _WINDOWS_OPENSCAD.is_file():
        return str(_WINDOWS_OPENSCAD)
    raise SystemExit(
        "OpenSCAD not found. Set the OPENSCAD environment variable, add "
        "\"openscad\" to local-paths.json, or put openscad on PATH.")


OPENSCAD = _openscad()


def refs(kind):
    """Directory holding the reference STLs for one part family.

    kind is "drawer" or "shell". The environment variable is
    MULTIBIN_REFS_<KIND>, for example MULTIBIN_REFS_SHELL.
    """
    env = f"MULTIBIN_REFS_{kind.upper()}"
    value = os.environ.get(env) or _local().get("refs", {}).get(kind)
    if not value:
        raise SystemExit(
            f"No reference directory for '{kind}'. Set {env}, or add "
            f"\"refs\": {{\"{kind}\": \"<folder>\"}} to {LOCAL_CONFIG.name}. "
            f"The reference STLs are MultiBuild's files and are not in this "
            f"repository; download them from https://multibuild.io.")
    path = Path(value)
    if not path.is_dir():
        raise SystemExit(f"{env} points to a missing directory: {path}")
    return path


def out_dir(*parts):
    """A directory under .local-build/out/, created on first use."""
    path = BUILD.joinpath("out", *parts)
    path.mkdir(parents=True, exist_ok=True)
    return path

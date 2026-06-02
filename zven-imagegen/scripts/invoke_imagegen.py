#!/usr/bin/env python3
"""Cross-platform wrapper for the bundled image generation helper."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import venv
from pathlib import Path


ENV_FILES = (".agentonlyenv", ".imagegen.env", ".env.imagegen")


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = value.strip().rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


def find_project_env_file(start: Path) -> Path | None:
    directory = start.resolve()
    while True:
        for name in ENV_FILES:
            candidate = directory / name
            if candidate.exists():
                return candidate
        if directory.parent == directory:
            return None
        directory = directory.parent


def parse_dotenv(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        values[match.group(1)] = value
    return values


def config_base_url(home: Path) -> str | None:
    config_path = home / "config.toml"
    if not config_path.exists():
        return None
    match = re.search(
        r'(?m)^\s*base_url\s*=\s*"([^"]+)"',
        config_path.read_text(encoding="utf-8"),
    )
    if not match:
        return None
    return match.group(1)


def auth_api_key(home: Path) -> str | None:
    auth_path = home / "auth.json"
    if not auth_path.exists():
        return None
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    value = auth.get("OPENAI_API_KEY")
    return value if isinstance(value, str) and value else None


def has_flag(args: list[str], name: str) -> bool:
    return any(arg == name or arg.startswith(f"{name}=") for arg in args)


def managed_python() -> Path:
    skill_dir = script_dir().parent
    venv_dir = skill_dir / ".venv"
    python = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )
    if python.exists():
        return python

    bootstrap = Path(os.environ.get("IMAGEGEN_PYTHON") or sys.executable)
    print("Creating zven-imagegen managed Python environment...", file=sys.stderr)
    if os.environ.get("IMAGEGEN_PYTHON"):
        subprocess.run([str(bootstrap), "-m", "venv", str(venv_dir)], check=True)
    else:
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    if not python.exists():
        subprocess.run([str(bootstrap), "-m", "venv", str(venv_dir)], check=True)
    if not python.exists():
        die(f"Managed Python environment was created, but no Python executable was found in {venv_dir}.")
    return python


def can_import_openai(python: Path) -> bool:
    check = (
        "import importlib.util, sys; "
        "sys.exit(0 if importlib.util.find_spec('openai') else 1)"
    )
    return subprocess.run(
        [str(python), "-c", check],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def ensure_openai(python: Path) -> None:
    if can_import_openai(python):
        return
    print("Installing zven-imagegen dependency: openai>=2.0.0...", file=sys.stderr)
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "openai>=2.0.0",
        ],
        check=True,
    )


def run_helper(python: Path, helper: Path, args: list[str], env: dict[str, str] | None = None) -> int:
    child_env = os.environ.copy()
    if env:
        child_env.update(env)
    return subprocess.run([str(python), str(helper), *args], env=child_env, check=False).returncode


def main(argv: list[str]) -> int:
    helper = script_dir() / "imagegen_stream.py"
    if not helper.exists():
        die("No image generation helper found next to this wrapper.")

    if has_flag(argv, "--dry-run"):
        return run_helper(Path(sys.executable), helper, argv)

    project_env = parse_dotenv(find_project_env_file(Path.cwd()))
    home = codex_home()
    api_key = (
        os.environ.get("IMAGEGEN_OPENAI_API_KEY")
        or project_env.get("IMAGEGEN_OPENAI_API_KEY")
        or auth_api_key(home)
    )
    base_url = normalize_base_url(
        os.environ.get("IMAGEGEN_OPENAI_BASE_URL")
        or project_env.get("IMAGEGEN_OPENAI_BASE_URL")
        or config_base_url(home)
    )

    if not api_key:
        die("No image API key found. Set IMAGEGEN_OPENAI_API_KEY, or provide OPENAI_API_KEY in Codex auth.json.")
    if not base_url:
        die("No image base URL found. Set IMAGEGEN_OPENAI_BASE_URL, or configure base_url in Codex config.toml.")

    python = managed_python()
    ensure_openai(python)
    return run_helper(
        python,
        helper,
        argv,
        {
            "OPENAI_API_KEY": api_key,
            "OPENAI_BASE_URL": base_url,
            "IMAGEGEN_OPENAI_API_KEY": api_key,
            "IMAGEGEN_OPENAI_BASE_URL": base_url,
        },
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from n3rv.mcp.shared import resolve_runtime_settings


def _check_systemd() -> None:
    if not shutil.which("systemctl"):
        print("Error: systemd not available (systemctl not found)", file=sys.stderr)
        raise SystemExit(1)


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
    )


def _unit_path(root: Path) -> Path:
    return root / ".n3rv" / "systemd" / "n3rv-hub.service"


def daemon_install(root: Path) -> int:
    _check_systemd()
    src = _unit_path(root)
    if not src.exists():
        print(f"Error: unit file not found at {src}", file=sys.stderr)
        print("Run 'n3rv init' first", file=sys.stderr)
        return 1
    dst_dir = Path.home() / ".config" / "systemd" / "user"
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / "n3rv-hub.service")
    result = _systemctl("daemon-reload")
    if result.returncode != 0:
        print(f"Error: daemon-reload failed: {result.stderr}", file=sys.stderr)
        return 1
    print("Hub daemon installed. Run 'n3rv daemon enable --now' to enable and start.")
    return 0


def daemon_start() -> int:
    _check_systemd()
    result = _systemctl("start", "n3rv-hub")
    if result.returncode != 0:
        print(f"Error: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print("Hub daemon started")
    return 0


def daemon_stop() -> int:
    _check_systemd()
    result = _systemctl("stop", "n3rv-hub")
    if result.returncode != 0:
        print(f"Error: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print("Hub daemon stopped")
    return 0


def daemon_status() -> int:
    _check_systemd()
    result = _systemctl("is-active", "n3rv-hub")
    print(result.stdout.strip())
    return 0 if result.returncode == 0 else 1


def daemon_enable(now: bool = False) -> int:
    _check_systemd()
    args = ["enable"]
    if now:
        args.append("--now")
    args.append("n3rv-hub")
    result = _systemctl(*args)
    if result.returncode != 0:
        print(f"Error: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print("Hub daemon enabled")
    return 0


def daemon_logs(root: Path) -> int:
    _check_systemd()
    settings = resolve_runtime_settings(root)
    log_file = settings.paths.log_file
    if log_file.exists():
        subprocess.run(["tail", "-f", str(log_file)])
        return 0
    result = _systemctl("status", "n3rv-hub")
    print(result.stdout)
    return 0

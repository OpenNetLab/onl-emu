#!/usr/bin/env python3
"""Manage the temporary tmpfs workdir."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKDIR = PROJECT_ROOT / "workdir"
UNMOUNT_ATTEMPTS = 10
UNMOUNT_RETRY_DELAY_SECONDS = 0.5


class Workdir:
    def __init__(
        self,
        path: Path,
        size_gb: int = 24,
        use_sudo: bool = True,
    ) -> None:
        if size_gb <= 0:
            raise ValueError("size_gb must be greater than zero")
        self.path = path.resolve()
        self.size_gb = size_gb
        self.use_sudo = use_sudo
        self._mounted = False

    def __enter__(self) -> Path:
        self.mount()
        return self.path

    def __exit__(self, *_args: object) -> None:
        self.close()

    def mount(self) -> None:
        if self._mounted:
            raise RuntimeError(f"workdir is already managed: {self.path}")
        self._require_commands()
        if self._is_mountpoint():
            raise RuntimeError(
                f"workdir is already mounted; refusing to reuse it: "
                f"{self.path}"
            )

        self.path.mkdir(parents=True, exist_ok=True)
        if any(self.path.iterdir()):
            raise RuntimeError(
                f"workdir must be empty before mounting: {self.path}"
            )

        options = (
            f"size={self.size_gb}G,uid={os.getuid()},gid={os.getgid()},"
            "mode=0755"
        )
        subprocess.run(
            [
                *self._privilege_prefix(),
                "mount",
                "-t",
                "tmpfs",
                "-o",
                options,
                "none",
                str(self.path),
            ],
            check=True,
        )
        if not self._is_mountpoint():
            raise RuntimeError(f"tmpfs mount was not created: {self.path}")
        self._mounted = True

    def close(self) -> None:
        if not self._mounted:
            return
        command = [
            *self._privilege_prefix(),
            "umount",
            "--",
            str(self.path),
        ]
        for attempt in range(UNMOUNT_ATTEMPTS):
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                break
            if attempt + 1 == UNMOUNT_ATTEMPTS:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(
                    f"failed to unmount workdir after "
                    f"{UNMOUNT_ATTEMPTS} attempts: {detail}"
                )
            time.sleep(UNMOUNT_RETRY_DELAY_SECONDS)
        if self._is_mountpoint():
            raise RuntimeError(f"workdir is still mounted: {self.path}")
        self._mounted = False
        self.path.rmdir()

    def _is_mountpoint(self) -> bool:
        return (
            subprocess.run(
                ["mountpoint", "-q", "--", str(self.path)],
                check=False,
            ).returncode
            == 0
        )

    def _privilege_prefix(self) -> list[str]:
        return ["sudo"] if self.use_sudo else []

    def _require_commands(self) -> None:
        for command in ("mountpoint", "mount", "umount"):
            if shutil.which(command) is None:
                raise RuntimeError(f"required command not found: {command}")
        if self.use_sudo and shutil.which("sudo") is None:
            raise RuntimeError("required command not found: sudo")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mount a temporary emulator workdir until interrupted."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_WORKDIR,
    )
    parser.add_argument("--size-gb", type=positive_int, default=24)
    parser.add_argument("--no-sudo", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    with Workdir(
        args.path,
        size_gb=args.size_gb,
        use_sudo=not args.no_sudo,
    ) as path:
        print(f"Mounted workdir at {path}. Press Enter to unmount.")
        input()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

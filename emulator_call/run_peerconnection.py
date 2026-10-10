#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALPHARTC_DIR = PROJECT_ROOT / "alphartc"
DEFAULT_WORKDIR = PROJECT_ROOT / "workdir"
DEFAULT_TC_SETUP = PROJECT_ROOT / "emulator_call" / "tc_setup.py"
SUPPORTED_MODELS = ("default", "gcc", "gemini", "hrcc")
ESTIMATOR_DIRS = {
    "gemini": PROJECT_ROOT / "models" / "Gemini",
    "hrcc": PROJECT_ROOT / "models" / "HRCC",
}


class PeerConnectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CallResult:
    sender_exit_code: int
    receiver_exit_code: int
    started_at: str
    finished_at: str
    duration_seconds: float


class PeerConnectionSession:
    def __init__(
        self,
        trace: Path,
        receiver_config: Path,
        sender_config: Path,
        workdir: Path,
        model: str,
        alphartc_dir: Path = DEFAULT_ALPHARTC_DIR,
        tc_setup: Path = DEFAULT_TC_SETUP,
        receiver_startup_delay: float = 1.0,
        network_ready_timeout: float = 5.0,
        call_timeout: Optional[float] = None,
        shutdown_timeout: float = 5.0,
    ) -> None:
        if receiver_startup_delay <= 0:
            raise ValueError(
                "receiver_startup_delay must be greater than zero"
            )
        if network_ready_timeout <= 0:
            raise ValueError(
                "network_ready_timeout must be greater than zero"
            )
        if call_timeout is not None and call_timeout <= 0:
            raise ValueError("call_timeout must be greater than zero")
        if shutdown_timeout <= 0:
            raise ValueError(
                "shutdown_timeout must be greater than zero"
            )
        if model not in SUPPORTED_MODELS:
            raise ValueError(
                f"model must be one of: {', '.join(SUPPORTED_MODELS)}"
            )

        self.trace = trace.resolve()
        self.receiver_config = receiver_config.resolve()
        self.sender_config = sender_config.resolve()
        self.workdir = workdir.resolve()
        self.model = model
        estimator_dir = ESTIMATOR_DIRS.get(model)
        self.estimator_dir = (
            estimator_dir.resolve() if estimator_dir is not None else None
        )
        self.alphartc_dir = alphartc_dir.resolve()
        self.tc_setup = tc_setup.resolve()
        self.receiver_startup_delay = receiver_startup_delay
        self.network_ready_timeout = network_ready_timeout
        self.call_timeout = call_timeout
        self.shutdown_timeout = shutdown_timeout

        self.wrapper = (
            self.alphartc_dir
            / "pyinfer"
            / "peerconnection_serverless"
        )
        self.gcc_binary = self.alphartc_dir / "exe" / "peerconnection_gcc"
        self.dll_dir = self.alphartc_dir / "dll"
        self.pyinfer_dir = self.alphartc_dir / "pyinfer"
        self.network_ready_file = self.workdir / "network.ready"

        self.network_process: Optional[subprocess.Popen[bytes]] = None
        self.receiver_process: Optional[subprocess.Popen[bytes]] = None
        self.sender_process: Optional[subprocess.Popen[bytes]] = None
        self._has_run = False

    def run(self) -> CallResult:
        if self._has_run:
            raise RuntimeError("PeerConnectionSession can only run once")
        self._has_run = True
        self._validate_inputs()

        try:
            self._start_network()
            self._wait_for_network_ready()
            self._start_receiver()
            self._wait_for_receiver_startup()

            started_wall = datetime.now(timezone.utc)
            started_monotonic = time.monotonic()
            self._start_sender()
            receiver_code, sender_code = self._wait_for_call(
                started_monotonic
            )
            finished_wall = datetime.now(timezone.utc)
            duration = time.monotonic() - started_monotonic

            result = CallResult(
                sender_exit_code=sender_code,
                receiver_exit_code=receiver_code,
                started_at=started_wall.isoformat(),
                finished_at=finished_wall.isoformat(),
                duration_seconds=round(duration, 3),
            )
            if receiver_code != 0 or sender_code != 0:
                raise PeerConnectionError(
                    "peer connection failed: "
                    f"receiver exit={receiver_code}, "
                    f"sender exit={sender_code}"
                )
            return result
        finally:
            self.close()

    def close(self) -> None:
        errors = []
        for process, label in (
            (self.sender_process, "sender"),
            (self.receiver_process, "receiver"),
            (self.network_process, "network emulator"),
        ):
            try:
                self._stop_process(process, label)
            except Exception as error:
                errors.append(error)
        self.network_ready_file.unlink(missing_ok=True)
        if errors:
            raise RuntimeError(
                f"failed to clean up {len(errors)} process(es)"
            ) from errors[0]

    def _validate_inputs(self) -> None:
        for path, label in (
            (self.trace, "trace"),
            (self.receiver_config, "receiver config"),
            (self.sender_config, "sender config"),
            (self.tc_setup, "tc setup"),
            (self._peer_executable(), "peer connection executable"),
        ):
            if not path.is_file():
                raise FileNotFoundError(f"{label} not found: {path}")
        if not self.dll_dir.is_dir():
            raise FileNotFoundError(
                f"AlphaRTC DLL directory not found: {self.dll_dir}"
            )
        if not self.workdir.is_dir():
            raise FileNotFoundError(
                f"workdir does not exist: {self.workdir}"
            )
        if self.estimator_dir is not None:
            estimator_file = (
                self.estimator_dir / "BandwidthEstimator.py"
            )
            if not estimator_file.is_file():
                raise FileNotFoundError(
                    "estimator entry point not found: "
                    f"{estimator_file}"
                )

    def _start_network(self) -> None:
        self.network_ready_file.unlink(missing_ok=True)
        log_path = self.workdir / "network.log"
        with log_path.open("wb") as log_file:
            self.network_process = subprocess.Popen(
                [
                    sys.executable,
                    str(self.tc_setup),
                    "--config",
                    str(self.trace),
                    "--ready-file",
                    str(self.network_ready_file),
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    def _wait_for_network_ready(self) -> None:
        if self.network_process is None:
            raise RuntimeError("network emulator was not started")
        deadline = time.monotonic() + self.network_ready_timeout
        while time.monotonic() < deadline:
            if self.network_ready_file.is_file():
                return
            exit_code = self.network_process.poll()
            if exit_code is not None:
                raise PeerConnectionError(
                    "network emulator exited before becoming ready "
                    f"with code {exit_code}; see "
                    f"{self.workdir / 'network.log'}"
                )
            time.sleep(0.01)
        raise TimeoutError(
            "timed out waiting for network emulator readiness; "
            f"see {self.workdir / 'network.log'}"
        )

    def _start_receiver(self) -> None:
        environment = self._peer_environment()
        if self.model != "gcc":
            environment["ESTIMATOR_LOG_PATH"] = str(
                self.workdir / "receiver_estimator.json"
            )
        log_path = self.workdir / "receiver_process.log"
        with log_path.open("wb") as log_file:
            self.receiver_process = subprocess.Popen(
                self._peer_command(self.receiver_config),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=environment,
                start_new_session=True,
            )

    def _wait_for_receiver_startup(self) -> None:
        if self.receiver_process is None:
            raise RuntimeError("receiver was not started")
        deadline = time.monotonic() + self.receiver_startup_delay
        while time.monotonic() < deadline:
            exit_code = self.receiver_process.poll()
            if exit_code is not None:
                raise PeerConnectionError(
                    "receiver exited during startup with code "
                    f"{exit_code}; see "
                    f"{self.workdir / 'receiver_process.log'}"
                )
            time.sleep(0.01)

    def _start_sender(self) -> None:
        log_path = self.workdir / "sender_process.log"
        with log_path.open("wb") as log_file:
            self.sender_process = subprocess.Popen(
                self._peer_command(self.sender_config),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=self._peer_environment(),
                start_new_session=True,
            )

    def _wait_for_call(
        self, started_monotonic: float
    ) -> tuple[int, int]:
        if self.receiver_process is None or self.sender_process is None:
            raise RuntimeError("sender and receiver must both be started")

        timeout = self.call_timeout
        if timeout is None:
            timeout = self._configured_call_timeout()
        deadline = started_monotonic + timeout

        while time.monotonic() < deadline:
            receiver_code = self.receiver_process.poll()
            sender_code = self.sender_process.poll()
            if receiver_code is not None and sender_code is not None:
                return receiver_code, sender_code
            if receiver_code not in (None, 0):
                raise PeerConnectionError(
                    f"receiver exited with code {receiver_code}; see "
                    f"{self.workdir / 'receiver_process.log'}"
                )
            if sender_code not in (None, 0):
                raise PeerConnectionError(
                    f"sender exited with code {sender_code}; see "
                    f"{self.workdir / 'sender_process.log'}"
                )
            time.sleep(0.05)

        raise TimeoutError(
            f"peer connection exceeded {timeout:.1f}s timeout"
        )

    def _configured_call_timeout(self) -> float:
        durations = [
            self._read_autoclose(self.receiver_config),
            self._read_autoclose(self.sender_config),
        ]
        if any(duration <= 0 for duration in durations):
            raise ValueError(
                "configs with autoclose=0 require an explicit call_timeout"
            )
        return float(max(durations) + 30)

    @staticmethod
    def _read_autoclose(config_path: Path) -> int:
        with config_path.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
        value = config.get("serverless_connection", {}).get("autoclose")
        if not isinstance(value, int):
            raise ValueError(
                f"invalid serverless_connection.autoclose in "
                f"{config_path}"
            )
        return value

    def _peer_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        if self.model == "gcc":
            return environment
        environment["LD_LIBRARY_PATH"] = self._prepend_path(
            str(self.dll_dir), environment.get("LD_LIBRARY_PATH")
        )
        environment["PYTHONPATH"] = self._prepend_path(
            str(self.pyinfer_dir), environment.get("PYTHONPATH")
        )
        if self.estimator_dir is not None:
            environment["ALPHARTC_ESTIMATOR_DIR"] = str(
                self.estimator_dir
            )
        else:
            environment.pop("ALPHARTC_ESTIMATOR_DIR", None)
        return environment

    def _peer_executable(self) -> Path:
        return self.gcc_binary if self.model == "gcc" else self.wrapper

    def _peer_command(self, config: Path) -> list[str]:
        if self.model == "gcc":
            return [str(self.gcc_binary), str(config)]
        return [sys.executable, str(self.wrapper), str(config)]

    @staticmethod
    def _prepend_path(value: str, current: Optional[str]) -> str:
        return f"{value}{os.pathsep}{current}" if current else value

    def _stop_process(
        self,
        process: Optional[subprocess.Popen[bytes]],
        label: str,
    ) -> None:
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=self.shutdown_timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=self.shutdown_timeout)
        except ProcessLookupError:
            return
        if process.poll() is None:
            raise RuntimeError(f"failed to stop {label}")


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one AlphaRTC peer connection session."
    )
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument(
        "--receiver-config", type=Path, required=True
    )
    parser.add_argument("--sender-config", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    parser.add_argument(
        "-m",
        "--model",
        choices=SUPPORTED_MODELS,
        required=True,
    )
    parser.add_argument(
        "--alphartc-dir", type=Path, default=DEFAULT_ALPHARTC_DIR
    )
    parser.add_argument(
        "--tc-setup", type=Path, default=DEFAULT_TC_SETUP
    )
    parser.add_argument(
        "--receiver-startup-delay",
        type=positive_float,
        default=1.0,
    )
    parser.add_argument(
        "--network-ready-timeout",
        type=positive_float,
        default=5.0,
    )
    parser.add_argument("--call-timeout", type=positive_float)
    parser.add_argument(
        "--shutdown-timeout", type=positive_float, default=5.0
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    result = PeerConnectionSession(
        trace=args.trace,
        receiver_config=args.receiver_config,
        sender_config=args.sender_config,
        workdir=args.workdir,
        model=args.model,
        alphartc_dir=args.alphartc_dir,
        tc_setup=args.tc_setup,
        receiver_startup_delay=args.receiver_startup_delay,
        network_ready_timeout=args.network_ready_timeout,
        call_timeout=args.call_timeout,
        shutdown_timeout=args.shutdown_timeout,
    ).run()
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

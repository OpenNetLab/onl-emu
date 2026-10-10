#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from .get_telemetry import write_telemetry
from .prepare_call import CallPreparer, PreparedCall
from .run_peerconnection import (
    SUPPORTED_MODELS,
    CallResult,
    PeerConnectionSession,
)
from .workdir import Workdir


FEEDBACK_STEP_MS = 200
TMPFS_SIZE_GB = 24
DEFAULT_MODEL = "default"
OUTPUT_FILES = (
    "telemetry.json",
    "receiver.log",
    "sender.log",
    "receiver_process.log",
    "sender_process.log",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2)
        output_file.write("\n")
    temporary.replace(path)


def validate_paths(
    trace: Path,
    media: Path,
    output_dir: Path,
    workdir: Path,
) -> None:
    if not trace.is_file():
        raise FileNotFoundError(f"trace not found: {trace}")
    if not media.is_file():
        raise FileNotFoundError(f"media not found: {media}")
    if output_dir == workdir or output_dir in workdir.parents:
        raise ValueError("output_dir must not contain workdir")
    if workdir in output_dir.parents:
        raise ValueError("output_dir must not be inside workdir")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(
            f"output directory must be empty: {output_dir}"
        )


def export_workdir(workdir: Path, output_dir: Path) -> None:
    for name in OUTPUT_FILES:
        source = workdir / name
        if source.is_file() and source.stat().st_size > 0:
            shutil.copy2(source, output_dir / name)


def run_emulator(
    trace: Path,
    media: Path,
    duration: int,
    output_dir: Path,
    workdir: Path,
    model: str,
) -> CallResult:
    if duration <= 0:
        raise ValueError("duration must be greater than zero")
    if model not in SUPPORTED_MODELS:
        raise ValueError(
            f"model must be one of: {', '.join(SUPPORTED_MODELS)}"
        )

    trace = trace.resolve()
    media = media.resolve()
    output_dir = output_dir.resolve()
    workdir = workdir.resolve()
    validate_paths(trace, media, output_dir, workdir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_metadata = {
        "status": "running",
        "trace": str(trace),
        "media": str(media),
        "duration_seconds": duration,
        "feedback_step_ms": FEEDBACK_STEP_MS,
        "model": model,
        "workdir": str(workdir),
        "output_dir": str(output_dir),
        "started_at": utc_now(),
    }
    write_json(output_dir / "run.json", run_metadata)

    call_result: Optional[CallResult] = None
    prepared: Optional[PreparedCall] = None
    try:
        with Workdir(workdir, size_gb=TMPFS_SIZE_GB) as mounted:
            try:
                prepared = CallPreparer(
                    media=media,
                    workdir=mounted,
                    call_length=duration,
                    feedback_step_ms=FEEDBACK_STEP_MS,
                    model=model,
                ).prepare()
                call_result = PeerConnectionSession(
                    trace=trace,
                    receiver_config=prepared.receiver_config,
                    sender_config=prepared.sender_config,
                    workdir=mounted,
                    model=model,
                ).run()
                write_telemetry(
                    prepared.receiver_log,
                    mounted / "telemetry.json",
                )
            finally:
                export_workdir(mounted, output_dir)
    except BaseException as error:
        run_metadata.update(
            {
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "finished_at": utc_now(),
            }
        )
        if call_result is not None:
            run_metadata["call"] = asdict(call_result)
        write_json(output_dir / "run.json", run_metadata)
        raise

    if call_result is None or prepared is None:
        raise RuntimeError("emulator completed without a call result")

    run_metadata.update(
        {
            "status": "success",
            "call": asdict(call_result),
            "finished_at": utc_now(),
        }
    )
    write_json(output_dir / "run.json", run_metadata)
    return call_result


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one complete AlphaRTC emulator call."
    )
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument(
        "--duration",
        type=positive_int,
        required=True,
        help="call duration in seconds",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument(
        "-m",
        "--model",
        choices=SUPPORTED_MODELS,
        default=DEFAULT_MODEL,
        help=(
            "bandwidth estimator model "
            f"(default: {DEFAULT_MODEL})"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    result = run_emulator(
        trace=args.trace,
        media=args.media,
        duration=args.duration,
        output_dir=args.output_dir,
        workdir=args.workdir,
        model=args.model,
    )
    print(
        f"Call completed in {result.duration_seconds:.3f}s; "
        f"results: {args.output_dir.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

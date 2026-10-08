#!/usr/bin/env python3
"""Calculate the reference benchmark QoE score."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence


class QoECalculator:
    """Calculate QoE for one emulator result."""

    JITTER_MAX_MS = 150.0

    def __init__(self, output_dir: Path) -> None:
        if not output_dir.is_dir():
            raise NotADirectoryError(
                f"emulator output directory not found: {output_dir}"
            )
        self.output_dir = output_dir
        self.telemetry_path = output_dir / "telemetry.json"
        self.run_path = output_dir / "run.json"

    def calculate(self) -> dict[str, float]:
        telemetry = self._read_json(self.telemetry_path)
        run = self._read_json(self.run_path)

        media_bitrate_kbps = self._number(
            telemetry,
            "MediaBitrateReceivedInKbps",
            self.telemetry_path,
            allow_zero=True,
        )
        jitter_delay_ms = self._number(
            telemetry,
            "JitterBufferDelayInMs",
            self.telemetry_path,
            allow_zero=True,
        )
        freeze_duration_ms = self._number(
            telemetry,
            "TotalFreezeDurationMs",
            self.telemetry_path,
            allow_zero=True,
        )
        duration_seconds = self._number(
            run, "duration_seconds", self.run_path
        )
        trace_path = self._run_file(run, "trace")
        media_path = self._run_file(run, "media")

        average_capacity_kbps = self._average_capacity_kbps(trace_path)
        source_bitrate_kbps = self._source_bitrate_kbps(media_path)

        bitrate_score = min(
            1.0,
            media_bitrate_kbps
            / min(average_capacity_kbps, source_bitrate_kbps),
        )
        jitter_score = max(
            0.0, 1.0 - jitter_delay_ms / self.JITTER_MAX_MS
        )
        freeze_score = max(
            0.0,
            1.0 - freeze_duration_ms / (duration_seconds * 1000.0),
        )
        qoe = 100.0 * (
            bitrate_score + jitter_score + freeze_score
        ) / 3.0
        return {
            "qoe": qoe,
            "bitrate_score": bitrate_score,
            "jitter_score": jitter_score,
            "freeze_score": freeze_score,
        }

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(f"JSON file not found: {path}")
        with path.open("r", encoding="utf-8") as input_file:
            data = json.load(input_file)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a JSON object")
        return data

    @staticmethod
    def _number(
        data: dict[str, Any],
        key: str,
        source: Path,
        *,
        allow_zero: bool = False,
    ) -> float:
        value = data.get(key)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            requirement = "non-negative" if allow_zero else "positive"
            raise ValueError(
                f"{source}: {key} must be a finite {requirement} number; "
                f"got {value!r}"
            )
        number = float(value)
        if number < 0 or (number == 0 and not allow_zero):
            requirement = "non-negative" if allow_zero else "positive"
            raise ValueError(
                f"{source}: {key} must be a finite {requirement} number; "
                f"got {value!r}"
            )
        return number

    def _run_file(self, run: dict[str, Any], key: str) -> Path:
        value = run.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"{self.run_path}: {key} must be a non-empty path"
            )
        path = Path(value)
        if not path.is_absolute():
            path = self.output_dir / path
        if not path.is_file():
            raise FileNotFoundError(f"{key} file not found: {path}")
        return path

    def _average_capacity_kbps(self, trace_path: Path) -> float:
        trace = self._read_json(trace_path)
        uplink = trace.get("uplink")
        if not isinstance(uplink, dict):
            raise ValueError(f"{trace_path}: uplink must be a JSON object")
        pattern = uplink.get("trace_pattern")
        if not isinstance(pattern, list) or not pattern:
            raise ValueError(
                f"{trace_path}: uplink.trace_pattern must be non-empty"
            )

        capacity_duration_sum = 0.0
        total_duration_ms = 0.0
        for index, segment in enumerate(pattern):
            if not isinstance(segment, dict):
                raise ValueError(
                    f"{trace_path}: trace_pattern[{index}] must be an object"
                )
            capacity = self._number(
                segment, "capacity", trace_path, allow_zero=True
            )
            duration = self._number(segment, "duration", trace_path)
            capacity_duration_sum += capacity * duration
            total_duration_ms += duration

        average = capacity_duration_sum / total_duration_ms
        if average <= 0:
            raise ValueError(
                f"{trace_path}: average uplink capacity must be positive"
            )
        return average

    @staticmethod
    def _source_bitrate_kbps(media_path: Path) -> float:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=bit_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(media_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            bitrate_kbps = float(result.stdout.strip()) / 1000.0
        except ValueError as error:
            raise ValueError(
                f"{media_path}: video stream has no valid bitrate"
            ) from error
        if not math.isfinite(bitrate_kbps) or bitrate_kbps <= 0:
            raise ValueError(
                f"{media_path}: video bitrate must be positive"
            )
        return bitrate_kbps


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print QoE and its component scores as JSON."
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="emulator output directory containing telemetry.json and run.json",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    print(json.dumps(QoECalculator(args.output_dir).calculate(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

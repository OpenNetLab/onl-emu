#!/usr/bin/env python3
"""Extract receiver telemetry."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Optional, Pattern, Sequence


TELEMETRY_PATTERNS: Dict[str, Pattern[str]] = {
    "MediaBitrateReceivedInKbps": re.compile(
        r"WebRTC\.Video\.MediaBitrateReceivedInKbps\s+(\d+)\s*$"
    ),
    "TotalFreezeDurationMs": re.compile(
        r"WebRTC\.Video\.TotalFreezeDurationMs\s+(\d+)\s*$"
    ),
    "InterframeDelayInMs": re.compile(
        r"WebRTC\.Video\.InterframeDelayInMs\s+(\d+)\s*$"
    ),
    "JitterBufferDelayInMs": re.compile(
        r"WebRTC\.Video\.JitterBufferDelayInMs\s+(\d+)\s*$"
    ),
    "AVSyncOffsetInMs": re.compile(
        r"WebRTC\.Video\.AVSyncOffsetInMs\s+(\d+)\s*$"
    ),
    "FramesDecoded": re.compile(r"Frames decoded\s+(\d+)\s*$"),
    "DroppedFrames": re.compile(
        r"WebRTC\.Video\.DroppedFrames\.Receiver\s+(\d+)\s*$"
    ),
    "RenderFramesPerSecond": re.compile(
        r"WebRTC\.Video\.RenderFramesPerSecond\s+(\d+)\s*$"
    ),
    "DecodedVp8Qp": re.compile(
        r"WebRTC\.Video\.Decoded\.Vp8\.Qp\s+(\d+)\s*$"
    ),
}


def get_telemetry(log: Path) -> Dict[str, Optional[int]]:
    if not log.is_file():
        raise FileNotFoundError(f"receiver log not found: {log}")

    telemetry: Dict[str, Optional[int]] = {
        key: None for key in TELEMETRY_PATTERNS
    }
    with log.open("r", encoding="utf-8", errors="replace") as log_file:
        for line in log_file:
            for key, pattern in TELEMETRY_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    telemetry[key] = int(match.group(1))
    if telemetry["TotalFreezeDurationMs"] is None:
        telemetry["TotalFreezeDurationMs"] = 0
    return telemetry


def write_telemetry(log: Path, output: Path) -> Dict[str, Optional[int]]:
    telemetry = get_telemetry(log)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as output_file:
        json.dump(telemetry, output_file, indent=2)
        output_file.write("\n")
    temporary.replace(output)
    return telemetry


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract core telemetry from receiver.log."
    )
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    telemetry = write_telemetry(args.log, args.output)
    missing = [key for key, value in telemetry.items() if value is None]
    if missing:
        print(
            "Telemetry written with missing fields: "
            + ", ".join(missing)
        )
    else:
        print(f"Telemetry written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare media and AlphaRTC call configurations."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKDIR = PROJECT_ROOT / "workdir"
SUPPORTED_MODELS = ("gcc", "gemini", "hrcc")


@dataclass(frozen=True)
class PreparedCall:
    source_media: Path
    video: Path
    audio: Path
    media_metadata: Path
    receiver_config: Path
    sender_config: Path
    receiver_log: Path
    sender_log: Path
    width: int
    height: int
    fps: int
    source_fps: str
    duration_seconds: int


@dataclass(frozen=True)
class CallPreparer:
    media: Path
    workdir: Path
    model: str
    call_length: int = 60
    feedback_step_ms: int = 200
    listening_ip: str = "0.0.0.0"
    destination_ip: str = "0.0.0.0"
    port: int = 8125
    save_received_media: bool = False
    overwrite: bool = False

    def __post_init__(self) -> None:
        if self.call_length <= 0:
            raise ValueError("call_length must be greater than zero")
        if self.feedback_step_ms <= 0:
            raise ValueError("feedback_step_ms must be greater than zero")
        if self.model not in SUPPORTED_MODELS:
            raise ValueError(
                f"model must be one of: {', '.join(SUPPORTED_MODELS)}"
            )
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.listening_ip:
            raise ValueError("listening_ip must not be empty")
        if not self.destination_ip:
            raise ValueError("destination_ip must not be empty")

    def prepare(self) -> PreparedCall:
        self._require_command("ffmpeg")
        self._require_command("ffprobe")
        if not self.media.is_file():
            raise FileNotFoundError(f"input media not found: {self.media}")
        if not self.workdir.is_dir():
            raise FileNotFoundError(
                f"workdir does not exist: {self.workdir}"
            )

        probe = self._probe_media()
        video_stream = self._find_stream(probe, "video")
        self._find_stream(probe, "audio")
        width, height = self._dimensions(video_stream)
        fps, source_fps = self._integer_fps(video_stream)
        media_duration = self._duration_seconds(probe)
        if (
            media_duration is not None
            and media_duration < self.call_length
        ):
            raise ValueError(
                f"input duration {media_duration:.3f}s is shorter than "
                f"call_length {self.call_length}s"
            )

        workdir = self.workdir.resolve()
        video = workdir / (
            "input.y4m" if self.model == "gcc" else "input.yuv"
        )
        audio = workdir / "input.wav"
        media_metadata = workdir / "media.json"
        receiver_config = workdir / "receiver_config.json"
        sender_config = workdir / "sender_config.json"
        receiver_log = workdir / "receiver.log"
        sender_log = workdir / "sender.log"
        generated_files = (
            video,
            audio,
            media_metadata,
            receiver_config,
            sender_config,
        )
        self._check_outputs(generated_files)

        self._convert_media(video, audio, fps)
        prepared = PreparedCall(
            source_media=self.media.resolve(),
            video=video,
            audio=audio,
            media_metadata=media_metadata,
            receiver_config=receiver_config,
            sender_config=sender_config,
            receiver_log=receiver_log,
            sender_log=sender_log,
            width=width,
            height=height,
            fps=fps,
            source_fps=source_fps,
            duration_seconds=self.call_length,
        )

        try:
            self._write_json(self._media_metadata(prepared), media_metadata)
            self._write_json(
                self._receiver_config(prepared), receiver_config
            )
            self._write_json(self._sender_config(prepared), sender_config)
        except BaseException:
            for path in generated_files:
                path.unlink(missing_ok=True)
            raise

        return prepared

    def _probe_media(self) -> dict[str, Any]:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(self.media),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    @staticmethod
    def _find_stream(
        probe: dict[str, Any], codec_type: str
    ) -> dict[str, Any]:
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == codec_type:
                return stream
        raise ValueError(f"input has no {codec_type} stream")

    @staticmethod
    def _dimensions(video_stream: dict[str, Any]) -> tuple[int, int]:
        width = video_stream.get("width")
        height = video_stream.get("height")
        if not isinstance(width, int) or not isinstance(height, int):
            raise ValueError("input video has invalid dimensions")
        if width <= 0 or height <= 0 or width % 2 or height % 2:
            raise ValueError(
                "I420 requires positive, even video dimensions; "
                f"got {width}x{height}"
            )
        return width, height

    @staticmethod
    def _integer_fps(
        video_stream: dict[str, Any],
    ) -> tuple[int, str]:
        source_fps = video_stream.get("avg_frame_rate")
        if (
            not isinstance(source_fps, str)
            or source_fps in {"0/0", "N/A"}
        ):
            source_fps = video_stream.get("r_frame_rate")
        if not isinstance(source_fps, str):
            raise ValueError("input video has no valid frame rate")

        fps = round(float(Fraction(source_fps)))
        if fps <= 0:
            raise ValueError(
                f"input video has invalid frame rate: {source_fps}"
            )
        return fps, source_fps

    @staticmethod
    def _duration_seconds(
        probe: dict[str, Any],
    ) -> Optional[float]:
        duration = probe.get("format", {}).get("duration")
        if not isinstance(duration, str):
            return None
        try:
            parsed = float(duration)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None

    def _check_outputs(self, outputs: tuple[Path, ...]) -> None:
        existing = [path for path in outputs if path.exists()]
        if existing and not self.overwrite:
            names = ", ".join(str(path) for path in existing)
            raise FileExistsError(
                f"output already exists: {names}; "
                "enable overwrite to replace"
            )

    def _convert_media(
        self, video: Path, audio: Path, fps: int
    ) -> None:
        video_output = [
            "-f",
            "yuv4mpegpipe" if self.model == "gcc" else "rawvideo",
            str(video),
        ]
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if self.overwrite else "-n",
            "-i",
            str(self.media),
            "-map",
            "0:v:0",
            "-t",
            str(self.call_length),
            "-vf",
            f"fps={fps}",
            "-pix_fmt",
            "yuv420p",
            *video_output,
            "-map",
            "0:a:0",
            "-t",
            str(self.call_length),
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(audio),
        ]
        try:
            subprocess.run(command, check=True)
        except BaseException:
            video.unlink(missing_ok=True)
            audio.unlink(missing_ok=True)
            raise

    def _media_metadata(
        self, prepared: PreparedCall
    ) -> dict[str, Any]:
        metadata = asdict(prepared)
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in metadata.items()
        }

    def _receiver_config(
        self, prepared: PreparedCall
    ) -> Dict[str, Any]:
        save_to_file: Dict[str, Any] = {
            "enabled": self.save_received_media
        }
        if self.save_received_media:
            save_to_file.update(
                {
                    "audio": {
                        "file_path": str(
                            prepared.audio.parent / "received.wav"
                        )
                    },
                    "video": {
                        "width": prepared.width,
                        "height": prepared.height,
                        "fps": prepared.fps,
                        "file_path": str(
                            prepared.video.parent / "received.yuv"
                        ),
                    },
                }
            )

        return {
            "serverless_connection": {
                "autoclose": self.call_length,
                "sender": {"enabled": False},
                "receiver": {
                    "enabled": True,
                    "listening_ip": self.listening_ip,
                    "listening_port": self.port,
                },
            },
            "bwe_feedback_duration": self.feedback_step_ms,
            "video_source": {
                "video_disabled": {"enabled": True},
                "webcam": {"enabled": False},
                "video_file": {"enabled": False},
            },
            "audio_source": {
                "microphone": {"enabled": False},
                "audio_file": {
                    "enabled": True,
                    "file_path": str(prepared.audio),
                },
            },
            "save_to_file": save_to_file,
            "logging": {
                "enabled": True,
                "log_output_path": str(prepared.receiver_log),
            },
        }

    def _sender_config(
        self, prepared: PreparedCall
    ) -> Dict[str, Any]:
        return {
            "serverless_connection": {
                "autoclose": self.call_length,
                "sender": {
                    "enabled": True,
                    "dest_ip": self.destination_ip,
                    "dest_port": self.port,
                },
                "receiver": {"enabled": False},
            },
            "bwe_feedback_duration": self.feedback_step_ms,
            "video_source": {
                "video_disabled": {"enabled": False},
                "webcam": {"enabled": False},
                "video_file": {
                    "enabled": True,
                    "height": prepared.height,
                    "width": prepared.width,
                    "fps": prepared.fps,
                    "file_path": str(prepared.video),
                },
            },
            "audio_source": {
                "microphone": {"enabled": False},
                "audio_file": {
                    "enabled": True,
                    "file_path": str(prepared.audio),
                },
            },
            "save_to_file": {"enabled": False},
            "logging": {
                "enabled": True,
                "log_output_path": str(prepared.sender_log),
            },
        }

    @staticmethod
    def _write_json(config: Dict[str, Any], output: Path) -> None:
        with output.open("w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=2)
            config_file.write("\n")

    @staticmethod
    def _require_command(command: str) -> None:
        if shutil.which(command) is None:
            raise RuntimeError(f"required command not found: {command}")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def valid_port(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return parsed


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare emulator media and sender/receiver configurations."
        )
    )
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument(
        "--workdir",
        type=Path,
        default=DEFAULT_WORKDIR,
    )
    parser.add_argument("--call-length", type=positive_int, default=60)
    parser.add_argument(
        "--feedback-step-ms", type=positive_int, default=200
    )
    parser.add_argument(
        "-m",
        "--model",
        choices=SUPPORTED_MODELS,
        required=True,
        help="bandwidth estimator model",
    )
    parser.add_argument("--listening-ip", default="0.0.0.0")
    parser.add_argument("--destination-ip", default="0.0.0.0")
    parser.add_argument("--port", type=valid_port, default=8125)
    parser.add_argument("--save-received-media", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    prepared = CallPreparer(
        media=args.media,
        workdir=args.workdir,
        call_length=args.call_length,
        feedback_step_ms=args.feedback_step_ms,
        model=args.model,
        listening_ip=args.listening_ip,
        destination_ip=args.destination_ip,
        port=args.port,
        save_received_media=args.save_received_media,
        overwrite=args.overwrite,
    ).prepare()
    print(
        f"Prepared {prepared.width}x{prepared.height} "
        f"{prepared.fps}fps media and configs in "
        f"{prepared.video.parent}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

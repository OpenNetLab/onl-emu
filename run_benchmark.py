#!/usr/bin/env python3
"""Run the fixed RTC evaluation benchmark sequentially."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from emulator_call import run_emulator
from emulator_call.run_peerconnection import SUPPORTED_MODELS, CallResult


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_WORKDIR = PROJECT_ROOT / "workdir"
CASE_COOLDOWN_SECONDS = 5
TRACE_CATEGORIES = (
    "HIGH_DYNAMIC",
    "HIGH_STABLE",
    "LOW_DYNAMIC",
    "LOW_STABLE",
    "MID_DYNAMIC",
    "MID_STABLE",
    "MID_UNKNOWN",
    "MIXED_DYNAMIC",
    "MIXED_STABLE",
    "MIXED_UNKNOWN",
)


@dataclass(frozen=True)
class BenchmarkCase:
    model: str
    media: Path
    trace: Path
    dataset: str
    category: str
    output_dir: Path

    @property
    def label(self) -> str:
        return (
            f"{self.model}/{self.media.stem}/{self.dataset}/"
            f"{self.trace.stem}"
        )


class WorkdirStateError(RuntimeError):
    pass


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def trace_category(path: Path) -> str:
    for category in TRACE_CATEGORIES:
        if path.stem.endswith(f"_{category}"):
            return category
    raise ValueError(f"cannot determine trace category: {path}")


def validate_requested(
    requested: Optional[Sequence[str]],
    available: set[str],
    label: str,
) -> Optional[set[str]]:
    if requested is None:
        return None
    selected = set(requested)
    unknown = selected - available
    if unknown:
        values = ", ".join(sorted(unknown))
        choices = ", ".join(sorted(available))
        raise ValueError(
            f"unknown {label}: {values}; available values: {choices}"
        )
    return selected


def discover_cases(
    benchmark_dir: Path,
    results_dir: Path,
    models: Sequence[str],
    media_names: Optional[Sequence[str]] = None,
    datasets: Optional[Sequence[str]] = None,
    categories: Optional[Sequence[str]] = None,
) -> list[BenchmarkCase]:
    if len(set(models)) != len(models):
        raise ValueError("models must not contain duplicates")
    unsupported_models = set(models) - set(SUPPORTED_MODELS)
    if unsupported_models:
        values = ", ".join(sorted(unsupported_models))
        raise ValueError(f"unsupported models: {values}")

    media_dir = benchmark_dir / "media"
    traces_dir = benchmark_dir / "traces"
    media_files = sorted(media_dir.glob("*.mp4"))
    trace_files = sorted(traces_dir.glob("*/*.json"))
    if not media_files:
        raise FileNotFoundError(f"no benchmark media found in {media_dir}")
    if not trace_files:
        raise FileNotFoundError(f"no benchmark traces found in {traces_dir}")

    available_media = {path.stem for path in media_files}
    available_datasets = {path.parent.name for path in trace_files}
    trace_categories = {path: trace_category(path) for path in trace_files}
    available_categories = set(trace_categories.values())

    selected_media = validate_requested(
        media_names, available_media, "media"
    )
    selected_datasets = validate_requested(
        datasets, available_datasets, "dataset"
    )
    selected_categories = validate_requested(
        categories, available_categories, "category"
    )

    if selected_media is not None:
        media_files = [
            path for path in media_files if path.stem in selected_media
        ]
    trace_files = [
        path
        for path in trace_files
        if (
            selected_datasets is None
            or path.parent.name in selected_datasets
        )
        and (
            selected_categories is None
            or trace_categories[path] in selected_categories
        )
    ]

    cases = []
    for model in models:
        for media in media_files:
            for trace in trace_files:
                dataset = trace.parent.name
                cases.append(
                    BenchmarkCase(
                        model=model,
                        media=media,
                        trace=trace,
                        dataset=dataset,
                        category=trace_categories[trace],
                        output_dir=(
                            results_dir
                            / model
                            / media.stem
                            / dataset
                            / trace.stem
                        ),
                    )
                )
    return cases


def successful_result(output_dir: Path) -> bool:
    run_path = output_dir / "run.json"
    if not run_path.is_file():
        return False
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read existing result: {run_path}") from error
    if not isinstance(run, dict):
        raise RuntimeError(f"existing result is not a JSON object: {run_path}")
    return run.get("status") == "success"


def ensure_workdir_clean(workdir: Path) -> None:
    if not workdir.exists():
        return
    if not workdir.is_dir():
        raise WorkdirStateError(f"workdir is not a directory: {workdir}")
    if workdir.is_mount():
        raise WorkdirStateError(f"workdir is still mounted: {workdir}")
    leftovers = sorted(path.name for path in workdir.iterdir())
    if leftovers:
        preview = ", ".join(leftovers[:5])
        if len(leftovers) > 5:
            preview += f", and {len(leftovers) - 5} more"
        raise WorkdirStateError(
            f"workdir contains residual files: {workdir}: {preview}"
        )


def cool_down_and_check_workdir(workdir: Path) -> None:
    print(
        f"Cooling down for {CASE_COOLDOWN_SECONDS} seconds before checking "
        "the workdir",
        flush=True,
    )
    time.sleep(CASE_COOLDOWN_SECONDS)
    ensure_workdir_clean(workdir)


def run_cases(
    cases: Sequence[BenchmarkCase],
    duration: int,
    workdir: Path,
    *,
    resume: bool = False,
    fail_fast: bool = False,
    runner: Callable[..., CallResult] = run_emulator,
) -> tuple[int, int, int]:
    succeeded = 0
    failed = 0
    skipped = 0
    total = len(cases)

    for index, case in enumerate(cases, 1):
        prefix = f"[{index}/{total}] {case.label}"
        try:
            if resume and successful_result(case.output_dir):
                skipped += 1
                print(f"{prefix}: skipped (already successful)")
                continue
            ensure_workdir_clean(workdir)
            if case.output_dir.exists() and any(case.output_dir.iterdir()):
                raise RuntimeError(
                    "output directory is not empty; move or remove the "
                    f"existing result before retrying: {case.output_dir}"
                )
        except WorkdirStateError as error:
            failed += 1
            print(
                f"{prefix}: failed before start: "
                f"{type(error).__name__}: {error}",
                file=sys.stderr,
                flush=True,
            )
            break
        except Exception as error:
            failed += 1
            print(
                f"{prefix}: failed before start: "
                f"{type(error).__name__}: {error}",
                file=sys.stderr,
                flush=True,
            )
            if fail_fast:
                break
            continue

        print(f"{prefix}: running", flush=True)
        run_error: Optional[Exception] = None
        try:
            runner(
                trace=case.trace,
                media=case.media,
                duration=duration,
                output_dir=case.output_dir,
                workdir=workdir,
                model=case.model,
            )
        except Exception as error:
            run_error = error

        try:
            cool_down_and_check_workdir(workdir)
        except Exception as cleanup_error:
            failed += 1
            if run_error is not None:
                print(
                    f"{prefix}: run failed: "
                    f"{type(run_error).__name__}: {run_error}",
                    file=sys.stderr,
                    flush=True,
                )
            print(
                f"{prefix}: workdir cleanup check failed; aborting "
                f"benchmark: {type(cleanup_error).__name__}: "
                f"{cleanup_error}",
                file=sys.stderr,
                flush=True,
            )
            break

        if run_error is not None:
            failed += 1
            print(
                f"{prefix}: failed: "
                f"{type(run_error).__name__}: {run_error}",
                file=sys.stderr,
                flush=True,
            )
            if fail_fast:
                break
            continue

        succeeded += 1
        print(f"{prefix}: success; workdir cleanup verified")

    return succeeded, failed, skipped


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed benchmark sequentially. Cases must not run in "
            "parallel because they share the loopback tc configuration."
        )
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=SUPPORTED_MODELS,
        required=True,
        help="one or more bandwidth estimators",
    )
    parser.add_argument(
        "--duration",
        type=positive_int,
        required=True,
        help="duration of each call in seconds",
    )
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=DEFAULT_BENCHMARK_DIR,
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=DEFAULT_WORKDIR,
    )
    parser.add_argument(
        "--media",
        nargs="+",
        help="media stems to include, for example Gameplay Mobile-cam",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        help="trace datasets to include",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        help="trace categories to include",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip cases whose run.json status is success",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="stop after the first failed case",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the selected plan without running cases",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        cases = discover_cases(
            benchmark_dir=args.benchmark_dir.resolve(),
            results_dir=args.results_dir.resolve(),
            models=args.models,
            media_names=args.media,
            datasets=args.datasets,
            categories=args.categories,
        )
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error)) from error

    if not cases:
        raise SystemExit("the selected filters produced no benchmark cases")

    media_count = len({case.media for case in cases})
    trace_count = len({case.trace for case in cases})
    print(
        f"Selected {len(args.models)} model(s), {media_count} media file(s), "
        f"and {trace_count} trace(s): {len(cases)} case(s)"
    )
    print(f"Results directory: {args.results_dir.resolve()}")
    print(f"Work directory: {args.workdir.resolve()}")
    if args.dry_run:
        return 0

    succeeded, failed, skipped = run_cases(
        cases,
        duration=args.duration,
        workdir=args.workdir.resolve(),
        resume=args.resume,
        fail_fast=args.fail_fast,
    )
    print(
        f"Benchmark complete: {succeeded} succeeded, {failed} failed, "
        f"{skipped} skipped"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

import importlib.util
import json
import os
import sys
from pathlib import Path

REQUEST_BANDWIDTH_COMMAND = "RequestBandwidth"
ESTIMATOR_DIR_ENV = "ALPHARTC_ESTIMATOR_DIR"


def load_estimator_class():
    estimator_dir = os.environ.get(ESTIMATOR_DIR_ENV)
    if estimator_dir is None:
        from estimator import Estimator

        return Estimator

    directory = Path(estimator_dir).resolve()
    estimator_file = directory / "BandwidthEstimator.py"
    if not estimator_file.is_file():
        raise FileNotFoundError(
            f"estimator entry point not found: {estimator_file}"
        )

    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location(
        "alphartc_custom_bandwidth_estimator",
        estimator_file,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load estimator: {estimator_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    estimator_class = getattr(module, "Estimator", None)
    if estimator_class is None:
        raise ImportError(
            f"Estimator class not found in {estimator_file}"
        )
    return estimator_class


def fetch_stats(line):
    try:
        return json.loads(line.strip())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def main(input_stream=sys.stdin.buffer, output_stream=sys.stdout.buffer, name=""):
    Estimator = load_estimator_class()
    estimator = Estimator()

    while True:
        line = input_stream.readline()
        if not line:
            break
        if isinstance(line, bytes):
            line = line.decode("utf-8")

        stats = fetch_stats(line)
        if stats is not None:
            estimator.report_states(stats)
        elif line.strip() == REQUEST_BANDWIDTH_COMMAND:
            bandwidth = estimator.get_estimated_bandwidth()
            output_stream.write(f"{int(bandwidth)}\n".encode("utf-8"))
            output_stream.flush()


if __name__ == "__main__":
    main(name=" ".join(sys.argv[1:]))
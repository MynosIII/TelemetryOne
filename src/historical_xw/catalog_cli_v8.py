from __future__ import annotations

import argparse
from pathlib import Path

from .visualizer_v8 import write_visualizer_catalog_v8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telemetry-one-catalog",
        description="Build a multi-dataset TelemetryOne static site from a catalog manifest.",
    )
    parser.add_argument("--catalog", default="dataset_catalog.json")
    parser.add_argument("--output-dir", default="public")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = write_visualizer_catalog_v8(Path(args.catalog), Path(args.output_dir))
    print(output.resolve())


if __name__ == "__main__":
    main()

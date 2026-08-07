from __future__ import annotations

import argparse
from pathlib import Path

from .visualizer_v8 import (
    infer_visualizer_source_label_v8,
    resolve_visualizer_inputs_v8,
    write_visualizer_v8,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="f1-visualizer-v8",
        description="Build the v8 GUI from any compatible, already-produced rating output.",
    )
    parser.add_argument(
        "--source-dir",
        default="data/outputs/rookie_backcast_v7_1",
        help="Directory containing existing retrospective history and ranking Parquets.",
    )
    parser.add_argument(
        "--history",
        help="Optional explicit history Parquet; overrides source-directory discovery.",
    )
    parser.add_argument(
        "--ranking",
        help="Optional explicit ranking Parquet; overrides source-directory discovery.",
    )
    parser.add_argument("--source-label", help="Optional dataset label shown in the GUI.")
    parser.add_argument("--output", help="Optional output HTML path.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    source_dir = Path(args.source_dir)
    history, ranking = resolve_visualizer_inputs_v8(
        source_dir,
        Path(args.history) if args.history else None,
        Path(args.ranking) if args.ranking else None,
    )
    effective_source_dir = history.parent if args.history else source_dir
    source_label = args.source_label or infer_visualizer_source_label_v8(
        effective_source_dir
    )
    output = (
        Path(args.output)
        if args.output
        else Path("data/outputs/visualizer_v8")
        / f"{effective_source_dir.name}_visualizer_v8.html"
    )
    output = write_visualizer_v8(
        history,
        ranking,
        output,
        source_label=source_label,
    )
    print(output.resolve())


if __name__ == "__main__":
    main()

"""Operator command for preserving the approved legacy Class 8 corpus.

These commands are never invoked by the web application. The project owner runs
them after installing dependencies and applying migrations.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ..database import SessionLocal
from .ingestion import ingest_into_database, write_manifest


async def _ingest(source_root: Path) -> None:
    async with SessionLocal() as session:
        summary = await ingest_into_database(session, source_root)
    print(
        "Ingested approved existing Class 8 corpus: "
        + ", ".join(f"{key}={value}" for key, value in summary.items())
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Lotus existing textbook ingestion")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("docs/resources/textbooks"),
        help="Directory containing class-8/Term1 and class-8/Term2",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Write a reviewable JSON manifest instead of changing the database",
    )
    args = parser.parse_args()
    if args.manifest:
        write_manifest(args.source_root, args.manifest)
        print(f"Wrote manifest to {args.manifest}")
        return
    asyncio.run(_ingest(args.source_root))


if __name__ == "__main__":
    main()

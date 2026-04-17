"""walkercreek registration entrypoint — mirrors the Cecret entrypoint."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from shared.jackpot_register_client import JackpotRegisterClient, RegistrationError
from shared.parsers import RunMetadata

from . import collect_files, parse

PIPELINE_NAME = "walkercreek"
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register walkercreek results with JACKPOT.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--pipeline-version", required=True)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    metadata = RunMetadata(
        run_id=args.run_id,
        pipeline_name=PIPELINE_NAME,
        pipeline_version=args.pipeline_version,
    )
    results = parse(args.output_dir, metadata)
    files = collect_files(args.output_dir, metadata)
    logger.info("parsed %d results and %d file artifacts", len(results), len(files))

    client = JackpotRegisterClient()
    failures = 0
    for result in results:
        try:
            client.register_result(result.result_type, result.payload)
        except RegistrationError:
            failures += 1
            logger.exception("register_result failed for %s", result.result_type)
    client.close()
    if failures:
        logger.error("%d result(s) failed to register", failures)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    sys.exit(main())

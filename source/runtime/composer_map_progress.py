"""Show existing-map validation progress before a migration workspace exists."""

from contextlib import contextmanager
import logging
from pathlib import Path
import re
from threading import Event, Thread
from time import monotonic
from runtime.composer_map_estimate import ComposerMapEstimate


@contextmanager
def composer_map_validation_progress(vault_root, *, interval_seconds=10):
    """Yield a note-progress callback and stop elapsed-time reporting on every exit."""
    logger = logging.getLogger(__name__)
    started = monotonic()
    stopped = Event()
    latest = "Reading map manifest and validating note hashes"
    estimate = None

    def report(message):
        nonlocal latest
        match = re.match(r"Validated (\d+) notes", message)
        if estimate is not None and match:
            message = estimate.update(int(match.group(1))) + " | " + message
        latest = message
        logger.info("Composer map validation: %s", message)

    def heartbeat():
        while not stopped.wait(interval_seconds):
            logger.info("Composer map validation still running after %.0f seconds: %s",
                        monotonic() - started, latest)

    logger.info("Validating existing Composer map: %s. This check can run before a migration workspace is created.", vault_root)
    worker = Thread(target=heartbeat, name="composer-map-validation-progress", daemon=True)
    worker.start()
    outcome = "interrupted"
    try:
        manifest_path = Path(vault_root) / "vault-manifest.json"
        if manifest_path.is_file():
            from tools.composer_mapper_tools.manifest_json_stream import iter_manifest_fields
            report("Counting notes in the map manifest before estimating validation time")
            total = 0
            for field, event, _ in iter_manifest_fields(manifest_path):
                if field == "entities" and event == "item":
                    total += 1
                    if total % 250 == 0:
                        report(f"Counting manifest notes: {total:,} found")
            report(f"Manifest count complete: {total:,} notes; starting note validation")
            estimate = ComposerMapEstimate(total)
        else:
            report("Checking legacy map structure; no manifest note count available")
        yield report
        outcome = "completed"
    finally:
        stopped.set()
        worker.join()
        logger.info("Composer map validation %s after %.1f seconds.", outcome, monotonic() - started)

"""
Ingest NYC TLC Parquet files from local disk to the Bronze layer of the GCS
data lake.

Idempotent: re-runs are safe. If the destination blob already exists with
the same size, the upload is skipped (override with --force).

Uses `gcloud storage` as the upload mechanism (via subprocess) and the
google-cloud-storage Python client only for metadata reads. This avoids a
known hang in the Python client's HTTP layer under WSL2.

Usage:
    python ingestion/ingest_to_gcs.py --year 2024 --month 1 --taxi-type yellow
    python ingestion/ingest_to_gcs.py --year 2024 --month 1 --taxi-type yellow --force
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from base64 import b64encode
from pathlib import Path


# ----- Configuration constants -----
BUCKET_NAME = "jjs-project-1-de-portfolio-datalake"
LOCAL_DATA_DIR = Path("data/raw")


# ----- Logging setup -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ingest_to_gcs")


def run_gcloud(args: list[str], timeout: float = 300.0) -> subprocess.CompletedProcess:
    """
    Run `gcloud ...` and return the completed process. Raises RuntimeError on
    non-zero exit. stdout/stderr captured for inspection.
    """
    cmd = ["gcloud"] + args
    log.debug("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gcloud command timed out after {timeout}s: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"gcloud failed (exit {result.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return result


def build_local_filename(taxi_type: str, year: int, month: int) -> str:
    """Filename pattern published by NYC TLC."""
    return f"{taxi_type}_tripdata_{year:04d}-{month:02d}.parquet"


def build_blob_uri(taxi_type: str, year: int, month: int, filename: str) -> str:
    """Full gs:// URI following the layered + Hive-style partitioning scheme."""
    return (
        f"gs://{BUCKET_NAME}/bronze/{taxi_type}_taxi/"
        f"year={year:04d}/month={month:02d}/{filename}"
    )


def compute_md5_b64(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    """
    Compute the MD5 of a local file and return it base64-encoded, matching the
    format that GCS reports in object metadata.
    """
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return b64encode(hasher.digest()).decode("ascii")


def describe_blob(blob_uri: str) -> dict | None:
    """
    Return blob metadata as a dict, or None if the blob does not exist.
    Uses `gcloud storage objects describe --format=json`.
    """
    try:
        result = run_gcloud(
            ["storage", "objects", "describe", blob_uri, "--format=json"],
            timeout=60.0,
        )
    except RuntimeError as exc:
        # `gcloud storage objects describe` returns non-zero with a clear
        # "not found" message when the object does not exist. Distinguish.
        if "not found" in str(exc).lower() or "404" in str(exc):
            return None
        raise

    return json.loads(result.stdout)


def should_skip_upload(blob_uri: str, local_size: int, force: bool) -> bool:
    """Decide whether the upload can be skipped because destination matches."""
    if force:
        log.info("Force flag set, will re-upload regardless of existing state")
        return False

    log.info("Checking destination: %s", blob_uri)
    meta = describe_blob(blob_uri)
    if meta is None:
        return False

    remote_size = int(meta.get("size", 0))
    if remote_size == local_size:
        log.info(
            "Destination already exists with matching size (%d bytes); skipping upload",
            remote_size,
        )
        return True

    log.warning(
        "Destination exists but size differs (local=%d, remote=%d); will re-upload",
        local_size,
        remote_size,
    )
    return False


def upload_with_verification(blob_uri: str, local_path: Path) -> None:
    """
    Upload via `gcloud storage cp`, then read back metadata via `gcloud storage
    objects describe` and verify size and MD5 match the local file.
    """
    log.info("Uploading %s -> %s", local_path, blob_uri)
    run_gcloud(
        ["storage", "cp", str(local_path), blob_uri],
        timeout=600.0,
    )

    meta = describe_blob(blob_uri)
    if meta is None:
        raise RuntimeError("Upload appeared to succeed but blob not found on describe")

    remote_size = int(meta.get("size", 0))
    remote_md5 = meta.get("md5_hash") or meta.get("md5Hash")

    local_size = local_path.stat().st_size
    local_md5 = compute_md5_b64(local_path)

    if remote_size != local_size:
        raise RuntimeError(
            f"Size mismatch after upload: local={local_size} remote={remote_size}"
        )

    if remote_md5 and remote_md5 != local_md5:
        raise RuntimeError(
            f"MD5 mismatch after upload: local={local_md5} remote={remote_md5}"
        )

    log.info(
        "Upload verified: size=%d bytes, md5=%s",
        remote_size,
        remote_md5 or "(not reported)",
    )


def ingest_month(taxi_type: str, year: int, month: int, force: bool) -> int:
    """End-to-end ingestion for one (taxi_type, year, month) tuple."""
    filename = build_local_filename(taxi_type, year, month)
    local_path = LOCAL_DATA_DIR / filename

    if not local_path.is_file():
        log.error(
            "Local file not found: %s. Download it first with curl from the "
            "NYC TLC public dataset.",
            local_path,
        )
        return 1

    local_size = local_path.stat().st_size
    log.info("Local file: %s (%.2f MB)", local_path, local_size / (1024 * 1024))

    blob_uri = build_blob_uri(taxi_type, year, month, filename)

    try:
        if should_skip_upload(blob_uri, local_size, force):
            log.info("Nothing to do.")
            return 0
        upload_with_verification(blob_uri, local_path)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1

    log.info("Done. %s", blob_uri)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest NYC TLC Parquet to GCS Bronze")
    parser.add_argument("--year", type=int, required=True, help="Year, e.g. 2024")
    parser.add_argument("--month", type=int, required=True, help="Month 1-12")
    parser.add_argument(
        "--taxi-type",
        choices=["yellow", "green"],
        default="yellow",
        help="Taxi type (default: yellow)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-upload even if destination already exists",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.month <= 12:
        log.error("Invalid month: %d", args.month)
        return 2
    return ingest_month(args.taxi_type, args.year, args.month, args.force)


if __name__ == "__main__":
    sys.exit(main())

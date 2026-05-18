"""
Ingest NYC TLC Parquet files from local disk to the Bronze layer of the GCS
data lake.

Idempotent: re-runs are safe. If the destination blob already exists with
the same size, the upload is skipped (override with --force).

Usage:
    python ingestion/ingest_to_gcs.py --year 2024 --month 1 --taxi-type yellow
    python ingestion/ingest_to_gcs.py --year 2024 --month 1 --taxi-type yellow --force
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from base64 import b64encode
from pathlib import Path
from typing import Optional

from google.cloud import storage
from google.api_core.exceptions import GoogleAPICallError, NotFound


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


def build_local_filename(taxi_type: str, year: int, month: int) -> str:
    """Filename pattern published by NYC TLC."""
    return f"{taxi_type}_tripdata_{year:04d}-{month:02d}.parquet"


def build_blob_path(taxi_type: str, year: int, month: int, filename: str) -> str:
    """GCS object path following the layered + Hive-style partitioning scheme."""
    return f"bronze/{taxi_type}_taxi/year={year:04d}/month={month:02d}/{filename}"


def compute_md5_b64(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    """
    Compute the MD5 of a local file and return it base64-encoded, matching the
    format that GCS reports in blob.md5_hash.
    """
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return b64encode(hasher.digest()).decode("ascii")


def should_skip_upload(
    bucket: storage.Bucket,
    blob_path: str,
    local_size: int,
    force: bool,
) -> bool:
    """
    Decide whether the upload can be skipped because the destination blob is
    already there and matches the local file size.
    """
    if force:
        log.info("Force flag set, will re-upload regardless of existing state")
        return False

    blob = bucket.blob(blob_path)
    if not blob.exists():
        return False

    blob.reload()  # populate size, md5, etc.
    if blob.size == local_size:
        log.info(
            "Destination already exists with matching size (%d bytes); skipping upload",
            blob.size,
        )
        return True

    log.warning(
        "Destination exists but size differs (local=%d, remote=%d); will re-upload",
        local_size,
        blob.size,
    )
    return False


def upload_with_verification(
    bucket: storage.Bucket,
    blob_path: str,
    local_path: Path,
) -> None:
    """
    Upload the file, then read back the blob metadata and verify size and MD5
    match the local file. Raises RuntimeError on mismatch.
    """
    blob = bucket.blob(blob_path)

    log.info("Uploading %s -> gs://%s/%s", local_path, bucket.name, blob_path)
    blob.upload_from_filename(str(local_path))

    blob.reload()
    local_size = local_path.stat().st_size
    local_md5 = compute_md5_b64(local_path)

    if blob.size != local_size:
        raise RuntimeError(
            f"Size mismatch after upload: local={local_size} remote={blob.size}"
        )

    if blob.md5_hash != local_md5:
        raise RuntimeError(
            f"MD5 mismatch after upload: local={local_md5} remote={blob.md5_hash}"
        )

    log.info(
        "Upload verified: size=%d bytes, md5=%s",
        blob.size,
        blob.md5_hash,
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

    try:
        client = storage.Client()
        bucket = client.get_bucket(BUCKET_NAME)
    except NotFound:
        log.error("Bucket %s not found", BUCKET_NAME)
        return 1
    except GoogleAPICallError as exc:
        log.error("Failed to access bucket: %s", exc)
        return 1

    blob_path = build_blob_path(taxi_type, year, month, filename)

    if should_skip_upload(bucket, blob_path, local_size, force):
        log.info("Nothing to do.")
        return 0

    try:
        upload_with_verification(bucket, blob_path, local_path)
    except (GoogleAPICallError, RuntimeError) as exc:
        log.error("Upload failed: %s", exc)
        return 1

    log.info("Done. gs://%s/%s", bucket.name, blob_path)
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

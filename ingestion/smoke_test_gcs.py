"""
Smoke test — verify that Python can authenticate to GCS via the Terraform
service account and round-trip a small file to the data lake bucket.

This is NOT a pipeline component. It is a one-off validation that the
authentication chain Python -> ADC -> GCS works end-to-end before we
write any real ingestion code.

Usage (with venv activated and GOOGLE_APPLICATION_CREDENTIALS set):
    python ingestion/smoke_test_gcs.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage
from google.api_core.exceptions import GoogleAPICallError, NotFound


BUCKET_NAME = "jjs-project-1-de-portfolio-datalake"
SMOKE_TEST_BLOB = "_smoke_test/hello_from_python.txt"


def main() -> int:
    # ----- Pre-flight checks -----
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS env var is not set.")
        print("Run: export GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/gcloud-keys/terraform-sa-jjs-project-1.json")
        return 1

    if not Path(creds_path).is_file():
        print(f"ERROR: Credentials file not found at {creds_path}")
        return 1

    print(f"[ok] credentials file: {creds_path}")

    # ----- Build the client -----
    try:
        client = storage.Client()
        print(f"[ok] storage client built; project={client.project}")
    except Exception as exc:  # broad: any auth failure surfaces here
        print(f"ERROR: failed to build GCS client: {exc}")
        return 1

    # ----- Resolve the bucket -----
    try:
        bucket = client.get_bucket(BUCKET_NAME)
        print(f"[ok] bucket resolved: gs://{bucket.name} (location={bucket.location})")
    except NotFound:
        print(f"ERROR: bucket {BUCKET_NAME!r} not found in project {client.project!r}")
        return 1
    except GoogleAPICallError as exc:
        print(f"ERROR: cannot access bucket {BUCKET_NAME!r}: {exc}")
        return 1

    # ----- Write a small object -----
    now = datetime.now(timezone.utc).isoformat()
    payload = (
        "Smoke test for jjs-project-1-de-portfolio data lake.\n"
        f"Written at: {now}\n"
        "If you can read this from gsutil/console, the chain Python -> SA -> GCS works.\n"
    )

    try:
        blob = bucket.blob(SMOKE_TEST_BLOB)
        blob.upload_from_string(payload, content_type="text/plain")
        print(f"[ok] uploaded gs://{bucket.name}/{SMOKE_TEST_BLOB} ({len(payload)} bytes)")
    except GoogleAPICallError as exc:
        print(f"ERROR: upload failed: {exc}")
        return 1

    # ----- Read it back to confirm -----
    try:
        downloaded = blob.download_as_text()
        if downloaded != payload:
            print("ERROR: round-trip mismatch — uploaded content differs from downloaded.")
            return 1
        print("[ok] round-trip read confirmed identical content")
    except GoogleAPICallError as exc:
        print(f"ERROR: download failed: {exc}")
        return 1

    print("\nSmoke test passed.")
    print(f"Inspect in console: https://console.cloud.google.com/storage/browser/{BUCKET_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
NYC MTA Subway Hourly Ridership Downloader
===========================================
Downloads MTA Subway Hourly Ridership data from the NY Open Data portal
via the Socrata API — the most granular public transit dataset available:
estimated ridership by station complex, payment method, and fare class
for every hour the subway operates (July 2020 onwards).

Datasets:
  2020–2024: https://data.ny.gov/Transportation/MTA-Subway-Hourly-Ridership-2020-2024/wujg-7c2s
  2025+:     https://data.ny.gov/Transportation/MTA-Subway-Hourly-Ridership-Beginning-2025/5wq4-mkjj

Columns: transit_timestamp, station_complex_id, station_complex, borough,
         payment_method, fare_class_category, ridership, transfers, lat, lon.

Usage:
    python download_nyc_traffic.py [--start 2024-01-01] [--end 2024-12-31]

Checkpointing:
    Progress is saved after every page (50k rows). If the process is killed,
    re-run with the same --start/--end flags to resume from the last checkpoint.
    The CSV is truncated to the last verified position before resuming, so a
    partially-written page is always discarded rather than corrupting the file.
"""

import csv
import json
import os
import sys
import argparse
import logging
from datetime import date
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

SOCRATA_BASE = "https://data.ny.gov/resource"

DATASET_2020_2024 = "wujg-7c2s"
DATASET_2025_PLUS = "5wq4-mkjj"

OUTPUT_DIR      = Path(__file__).parent / "data"
OUTPUT_FILE     = OUTPUT_DIR / "nyc_mta_hourly_ridership.csv"
CHECKPOINT_FILE = OUTPUT_DIR / "download_checkpoint.json"

PAGE_SIZE = 50_000

OUT_COLS = [
    "transit_timestamp",
    "transit_mode",
    "station_complex_id",
    "station_complex",
    "borough",
    "payment_method",
    "fare_class_category",
    "ridership",
    "transfers",
    "latitude",
    "longitude",
]

# ── Checkpoint ─────────────────────────────────────────────────────────────────

def load_checkpoint(start: date, end: date) -> dict | None:
    """Return saved checkpoint if it matches the requested date range, else None."""
    if not CHECKPOINT_FILE.exists():
        return None
    try:
        with open(CHECKPOINT_FILE) as f:
            cp = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if cp.get("start") != str(start) or cp.get("end") != str(end):
        log.info("Checkpoint date range mismatch — starting fresh.")
        return None
    return cp


def save_checkpoint(
    start: date,
    end: date,
    current_dataset: str,
    next_offset: int,
    csv_pos: int,
    rows_written: int,
    completed_datasets: list[str],
) -> None:
    """Atomically write checkpoint via temp-file rename (POSIX atomic)."""
    tmp = CHECKPOINT_FILE.with_suffix(".json.tmp")
    payload = {
        "start": str(start),
        "end": str(end),
        "current_dataset": current_dataset,
        "next_offset": next_offset,
        "csv_pos": csv_pos,
        "rows_written": rows_written,
        "completed_datasets": completed_datasets,
    }
    with open(tmp, "w") as f:
        json.dump(payload, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CHECKPOINT_FILE)


# ── Socrata API ────────────────────────────────────────────────────────────────

def fetch_page(dataset_id: str, start_ts: str, end_ts: str, offset: int) -> list[dict]:
    url = f"{SOCRATA_BASE}/{dataset_id}.json"
    params = {
        "$where":  f"transit_timestamp >= '{start_ts}' AND transit_timestamp <= '{end_ts}'",
        "$order":  "transit_timestamp ASC",
        "$limit":  PAGE_SIZE,
        "$offset": offset,
    }
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def stream_dataset(
    dataset_id: str,
    seg_start: date,
    seg_end: date,
    writer: csv.DictWriter,
    csv_file,
    resume_offset: int,
    rows_written: int,
    start: date,
    end: date,
    completed_datasets: list[str],
) -> int:
    """
    Page through one Socrata dataset, writing each complete page to the CSV
    immediately. Checkpoint is saved after each page so progress survives a kill.
    Returns the updated rows_written count.
    """
    start_ts = f"{seg_start}T00:00:00.000"
    end_ts   = f"{seg_end}T23:59:59.000"
    offset   = resume_offset

    while True:
        log.info("  [%s] offset=%-8d  fetching %d rows ...", dataset_id, offset, PAGE_SIZE)
        page = fetch_page(dataset_id, start_ts, end_ts, offset)
        if not page:
            break

        writer.writerows(page)
        csv_file.flush()
        os.fsync(csv_file.fileno())
        csv_pos = csv_file.tell()

        rows_written += len(page)
        save_checkpoint(start, end, dataset_id, offset + PAGE_SIZE,
                        csv_pos, rows_written, completed_datasets)
        log.info("  → wrote %d rows (running total: %d)", len(page), rows_written)

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return rows_written


# ── Main ───────────────────────────────────────────────────────────────────────

def main(start: date, end: date) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    cp = load_checkpoint(start, end)

    if cp and OUTPUT_FILE.exists():
        log.info(
            "Resuming from checkpoint: %d rows written, dataset=%s offset=%d",
            cp["rows_written"], cp["current_dataset"], cp["next_offset"],
        )
        # Drop any partial page that was written after the last checkpoint
        with open(OUTPUT_FILE, "r+", newline="") as f:
            f.seek(cp["csv_pos"])
            f.truncate()
        csv_mode         = "a"
        write_header     = False
        rows_written       = cp["rows_written"]
        completed_datasets = cp["completed_datasets"]
        checkpoint_dataset = cp["current_dataset"]
        checkpoint_offset  = cp["next_offset"]
    else:
        if cp:
            log.info("Checkpoint found but CSV missing — starting fresh.")
        csv_mode         = "w"
        write_header     = True
        rows_written       = 0
        completed_datasets = []
        checkpoint_dataset = None
        checkpoint_offset  = 0

    segments: list[tuple[str, date, date]] = []
    if start.year <= 2024:
        segments.append((DATASET_2020_2024, start, min(end, date(2024, 12, 31))))
    if end.year >= 2025:
        segments.append((DATASET_2025_PLUS, max(start, date(2025, 1, 1)), end))

    with open(OUTPUT_FILE, csv_mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLS, extrasaction="ignore")
        if write_header:
            writer.writeheader()

        for dataset_id, seg_start, seg_end in segments:
            if dataset_id in completed_datasets:
                log.info("Skipping %s (already complete)", dataset_id)
                continue

            resume_offset = checkpoint_offset if checkpoint_dataset == dataset_id else 0

            log.info("=== dataset=%s  %s → %s  (offset %d) ===",
                     dataset_id, seg_start, seg_end, resume_offset)

            rows_written = stream_dataset(
                dataset_id, seg_start, seg_end,
                writer, f,
                resume_offset, rows_written,
                start, end,
                completed_datasets,
            )

            completed_datasets.append(dataset_id)
            save_checkpoint(start, end, dataset_id, 0, f.tell(),
                            rows_written, completed_datasets)
            log.info("=== dataset=%s complete ===", dataset_id)

    if rows_written == 0:
        log.error("No data returned — check date range and network.")
        sys.exit(1)

    CHECKPOINT_FILE.unlink(missing_ok=True)
    CHECKPOINT_FILE.with_suffix(".json.tmp").unlink(missing_ok=True)
    log.info("Done. %d rows → %s", rows_written, OUTPUT_FILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download NYC MTA subway hourly ridership via NY Open Data (Socrata)."
    )
    parser.add_argument(
        "--start", default="2024-01-01", metavar="YYYY-MM-DD",
        help="Start date (default: 2024-01-01)",
    )
    parser.add_argument(
        "--end", default=date.today().isoformat(), metavar="YYYY-MM-DD",
        help="End date (default: today)",
    )
    args = parser.parse_args()
    main(
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
    )

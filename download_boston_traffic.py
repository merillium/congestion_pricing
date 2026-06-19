"""
Boston-Area Traffic Data Downloader
====================================
Downloads FHWA TMAS (Travel Monitoring Analysis System) data for
Massachusetts continuous count stations (2010–2025), filters to
Boston-area counties, and saves a combined CSV.

Data source: https://www.fhwa.dot.gov/policyinformation/tables/tmasdata/
FHWA TMG documentation: https://www.fhwa.dot.gov/policyinformation/tmguide/

Usage:
    python download_boston_traffic.py [--years 2020 2021 2022 2023 2024]
"""

import requests
import zipfile
import io
import csv
import os
import sys
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

FHWA_BASE = "https://www.fhwa.dot.gov/policyinformation/tables/tmasdata"

# Massachusetts state FIPS code
MA_FIPS = "25"

# Boston-area county FIPS (3-digit, zero-padded)
BOSTON_COUNTIES = {
    "009",  # Essex
    "017",  # Middlesex
    "021",  # Norfolk
    "025",  # Suffolk (City of Boston)
    "023",  # Plymouth
}

OUTPUT_DIR = Path(__file__).parent / "data"
STATION_FILE = OUTPUT_DIR / "ma_tmas_stations.csv"
VOLUME_FILE  = OUTPUT_DIR / "boston_tmas_traffic.csv"

MONTHS = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
]

MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3,  "apr": 4,  "may": 5,  "jun": 6,
    "jul": 7, "aug": 8, "sep": 9,  "oct": 10, "nov": 11, "dec": 12,
}

# ── Helper: download + unzip ──────────────────────────────────────────────────

def fetch_zip(url: str, desc: str) -> dict[str, bytes]:
    """Download a zip from url and return {filename: content} dict."""
    log.info("Downloading %s …", desc)
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        log.warning("  Not found (404): %s", url)
        return {}
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        return {name: z.read(name) for name in z.namelist()}


# ── Station data ──────────────────────────────────────────────────────────────

def parse_station_file_2020plus(raw: bytes) -> list[dict]:
    """Parse pipe-delimited station file (2020+)."""
    rows = []
    text = raw.decode("latin-1", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for row in reader:
        state = row.get("STATE", row.get("State_FIPS", row.get("State_Code", ""))).strip().zfill(2)
        if state != MA_FIPS:
            continue
        county = row.get("COUNTY", row.get("County", row.get("County_Code", ""))).strip().zfill(3)
        if county not in BOSTON_COUNTIES:
            continue
        rows.append(row)
    return rows


def parse_station_file_pre2020(raw: bytes) -> list[dict]:
    """
    Parse fixed-width station file (pre-2020).
    Field positions from FHWA 2001 TMG Chapter 7, Section 7.2.
    """
    # Column positions (0-based, inclusive start, exclusive end)
    FIELDS = [
        ("fips_state",   0,   2),
        ("station_id",   2,   8),
        ("direction",    8,   9),
        ("lane",         9,  10),
        ("year",        10,  14),
        ("fc",          14,  16),
        ("num_lanes",   16,  17),
        ("sample_type", 17,  18),
        ("lanes_vol",   18,  19),
        ("lanes_cls",   19,  20),
        ("lanes_wgt",   20,  21),
        ("yr_estab",    21,  25),
        ("yr_disc",     25,  29),
        ("county",      29,  32),
        ("hpms",        32,  33),
        ("lat",         33,  42),
        ("lon",         42,  51),
    ]
    rows = []
    text = raw.decode("latin-1", errors="replace")
    for line in text.splitlines():
        if len(line) < 33:
            continue
        state = line[0:2].strip().zfill(2)
        if state != MA_FIPS:
            continue
        county = line[29:32].strip().zfill(3)
        if county not in BOSTON_COUNTIES:
            continue
        row = {name: line[s:e].strip() for name, s, e in FIELDS}
        rows.append(row)
    return rows


def get_stations(year: int) -> list[dict]:
    """Download station data for the given year and return MA/Boston rows."""
    url = f"{FHWA_BASE}/{year}/{year}_station_data.zip"
    files = fetch_zip(url, f"{year} station data")
    if not files:
        return []
    log.debug("  Zip contents for %d: %s", year, list(files.keys()))

    # Prefer the MA-specific file when the zip is split per state (2022+)
    ma_key = next((k for k in files if "/MA_" in k or k.startswith("MA_")), None)
    candidates = [ma_key] if ma_key else list(files.keys())

    for fname in candidates:
        content = files[fname]
        log.debug("  Checking file: %s (size=%d)", fname, len(content))
        ext = fname.rsplit(".", 1)[-1].lower()
        if ext in ("dbf",):
            log.debug("  Skipping %s — dbf binary", fname)
            continue
        if ext not in ("txt", "csv", "sta"):
            log.debug("  Skipping %s — unrecognised extension .%s", fname, ext)
            continue
        sample = content[:500].decode("latin-1", errors="replace")
        log.debug("  First 500 bytes of %s:\n%s", fname, sample)
        if year >= 2020:
            rows = parse_station_file_2020plus(content)
        else:
            rows = parse_station_file_pre2020(content)
        log.debug("  Parsed %d Boston-area rows from %s", len(rows), fname)
        if rows:
            log.info("  Found %d Boston-area MA stations in %d", len(rows), year)
            return rows
    return []


# ── Volume (CCS) data ─────────────────────────────────────────────────────────

def parse_volume_file_2020plus(raw: bytes, boston_station_ids: set[str]) -> list[dict]:
    """Parse pipe-delimited CCS volume file (2020+)."""
    text = raw.decode("latin-1", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    rows = []
    for row in reader:
        state = row.get("STATE", row.get("State_FIPS", row.get("State_Code", ""))).strip().zfill(2)
        if state != MA_FIPS:
            continue
        sid = row.get("StationID", row.get("STATIONID", row.get("Station_ID", row.get("Station_Id", "")))).strip()
        if boston_station_ids and sid not in boston_station_ids:
            continue
        rows.append(row)
    return rows


def parse_volume_file_pre2020(raw: bytes, boston_station_ids: set[str]) -> list[dict]:
    """
    Parse fixed-width CCS volume file (pre-2020).
    Fields from FHWA 2001 TMG Chapter 7, Section 7.3.
    """
    FIELDS = [
        ("fips_state",  0,   2),
        ("station_id",  2,   8),
        ("direction",   8,   9),
        ("lane",        9,  10),
        ("year",       10,  14),
        ("month",      14,  16),
        ("day_type",   16,  17),
    ]
    rows = []
    text = raw.decode("latin-1", errors="replace")
    for line in text.splitlines():
        if len(line) < 137:
            continue
        state = line[0:2].strip().zfill(2)
        if state != MA_FIPS:
            continue
        sid = line[2:8].strip()
        if boston_station_ids and sid not in boston_station_ids:
            continue
        row = {name: line[s:e].strip() for name, s, e in FIELDS}
        # Hours: columns 17-136, each 5 chars wide, hours 1-24
        for h in range(1, 25):
            col_start = 17 + (h - 1) * 5
            row[f"hour_{h:02d}"] = line[col_start:col_start + 5].strip()
        rows.append(row)
    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main(years: list[int]):
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── Step 1: Collect Boston-area station IDs ──────────────────────────────
    log.info("=== Step 1: Finding Boston-area TMAS stations ===")

    def norm(row, *keys):
        for k in keys:
            if k in row:
                return row[k].strip()
        return ""

    all_station_rows = []
    if STATION_FILE.exists():
        log.info("Loading station data from cache: %s", STATION_FILE)
        with open(STATION_FILE, newline="") as f:
            all_station_rows = list(csv.DictReader(f))
        log.info("  Loaded %d cached station rows", len(all_station_rows))
    else:
        for y in sorted(years, reverse=True):
            rows = get_stations(y)
            if rows:
                all_station_rows = rows
                break

        if not all_station_rows:
            log.error("Could not retrieve station data. Check network and try again.")
            sys.exit(1)

        with open(STATION_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_station_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_station_rows)
        log.info("Station metadata → %s", STATION_FILE)

    boston_station_ids = set()
    for r in all_station_rows:
        sid = norm(r, "station_id", "StationID", "STATIONID", "Station_ID", "Station_Id")
        if sid:
            boston_station_ids.add(sid)

    log.info("Boston-area station IDs (%d): %s", len(boston_station_ids), sorted(boston_station_ids))

    # ── Step 2: Download monthly volume data ─────────────────────────────────
    log.info("=== Step 2: Downloading monthly traffic volumes ===")

    all_volume_rows = []
    for year in sorted(years):
        for month_abbr in MONTHS:
            # URL pattern differs slightly by year
            if year >= 2020:
                url = f"{FHWA_BASE}/{year}/{month_abbr}_{year}_ccs_data.zip"
            elif year >= 2012:
                url = f"{FHWA_BASE}/{year}/{month_abbr}_{year}_ccs_data.zip"
            else:  # 2011
                url = f"{FHWA_BASE}/{year}/{month_abbr}_{year}_ccs_data.zip"

            files = fetch_zip(url, f"{year}-{month_abbr}")
            if not files:
                continue

            log.debug("  Volume zip contents for %d-%s: %s", year, month_abbr, list(files.keys()))
            for fname, content in files.items():
                ext = fname.rsplit(".", 1)[-1].lower()
                if ext not in ("txt", "csv", "sta"):
                    log.debug("  Skipping volume file %s — extension .%s", fname, ext)
                    continue
                sample = content[:300].decode("latin-1", errors="replace")
                log.debug("  First 300 bytes of %s:\n%s", fname, sample)
                if year >= 2020:
                    rows = parse_volume_file_2020plus(content, boston_station_ids)
                else:
                    rows = parse_volume_file_pre2020(content, boston_station_ids)

                log.debug("  Parsed %d Boston rows from %s", len(rows), fname)
                for r in rows:
                    r.setdefault("_year",  str(year))
                    r.setdefault("_month", str(MONTH_NAMES[month_abbr]))
                all_volume_rows.extend(rows)
                log.info("  %d-%s → %d Boston rows (total so far: %d)",
                         year, month_abbr, len(rows), len(all_volume_rows))
                break  # only one data file per zip

    # ── Step 3: Save combined CSV ─────────────────────────────────────────────
    log.info("=== Step 3: Saving combined CSV ===")

    if not all_volume_rows:
        log.error("No volume data found. Check URLs and network connectivity.")
        sys.exit(1)

    # Collect all field names
    all_fields: list[str] = []
    seen: set[str] = set()
    for row in all_volume_rows:
        for k in row:
            if k not in seen:
                all_fields.append(k)
                seen.add(k)

    with open(VOLUME_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_volume_rows)

    log.info("✓ Traffic volume data → %s  (%d rows)", VOLUME_FILE, len(all_volume_rows))
    log.info("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Boston-area TMAS traffic data.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=list(range(2020, 2026)),
        help="Years to download (default: 2020–2025)",
    )
    args = parser.parse_args()
    main(args.years)

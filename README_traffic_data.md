# Boston-Area Traffic Data

## Source
**FHWA TMAS (Travel Monitoring Analysis System)**  
https://www.fhwa.dot.gov/policyinformation/tables/tmasdata/

This is the federal government's continuous traffic count program. Massachusetts
DOT reports hourly vehicle counts from permanent roadway sensors to FHWA monthly.
Data runs from 2010–2025.

## What You Get
- **Station locations**: permanent sensor locations in Boston-area counties
  (Suffolk, Middlesex, Norfolk, Essex, Plymouth)
- **Hourly traffic volumes**: vehicles per hour, per direction, per lane, per day
- **Coverage**: 2020–2025 by default (data back to 2010 also available)

## Files
| File | Contents |
|------|----------|
| `data/ma_tmas_stations.csv` | Sensor metadata (location, road class, county) |
| `data/boston_tmas_traffic.csv` | Hourly traffic counts for Boston-area stations |

## How to Download

1. **Install dependencies** (one time):
   ```bash
   pip install requests
   ```

2. **Run the downloader**:
   ```bash
   # Default: 2020–2025
   python download_boston_traffic.py

   # Specific years (e.g., all available history):
   python download_boston_traffic.py --years 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025
   ```

   Each year downloads ~12 monthly zip files (~5–15 MB each). Expect 5–20 minutes
   depending on your connection.

3. **Output** goes to the `data/` subfolder.

## Key Fields in the Volume CSV (2020+ format)
| Field | Description |
|-------|-------------|
| `STATE` | State FIPS (25 = Massachusetts) |
| `StationID` | Unique sensor ID |
| `Dir` | Direction of travel |
| `Lane` | Lane number |
| `Year` / `Month` | Time period |
| `hour_01` … `hour_24` | Vehicle counts per hour of day |

## Alternative Data Sources
If you want Boston-city-specific intersection counts (TMC / ATR studies going back to 1993), those are available through Analyze Boston:
https://data.boston.gov/dataset/traffic-related-data
(Files are stored in a document management system — browse and download individually.)

For statewide Massachusetts traffic volume trends (monthly summary, 1992–present), see:
https://www.fhwa.dot.gov/policyinformation/travel_monitoring/tvt.cfm

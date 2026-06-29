# NYC Congestion Pricing — Ridership Impact Analysis

This project estimates the effect of NYC's congestion pricing program on subway ridership by training a forecasting model on pre-policy data and comparing its predictions against post-policy actuals.

## Background

NYC's congestion pricing program took effect on **January 5, 2025**, charging drivers entering Manhattan south of 60th Street.[^1] A key expected benefit was a shift in commuters from cars to transit. This analysis attempts to quantify that shift using subway ridership data.

[^1]: Hu, Winnie; Ley, Ana (January 4, 2025). "Welcome to the Congestion Zone: New York Toll Program Is Set to Begin". *The New York Times*. ISSN 0362-4331. Retrieved June 27, 2026.

## Data Source

**NYC MTA Hourly Ridership**
- Hourly entry counts per subway station complex, sourced from the MTA's open data portal
- Stored at `data/nyc_mta_hourly_ridership.csv`

## How to Download Data

```bash
pip install requests
python3 -i download_nyc_traffic.py
```

## Methods

### Overview

The core idea is a **counterfactual forecast**: train a model on 2024 (pre-policy) ridership to learn each station's normal seasonal patterns, then project what 2025 ridership *would have been* without congestion pricing. The difference between the forecast and actual 2025 ridership is attributed to the policy.

```
lift = actual_2025 - predicted_2025
```

### Station Filtering

Only stations with at least **50,000 total riders in 2024** are included. This removes low-volume stations where noisy counts would dominate the signal.

### Model: Facebook Prophet

A separate [Prophet](https://facebook.github.io/prophet/) model is trained for each station using daily ridership aggregated from the hourly source data.

**Training data**: daily ridership per station, full year 2024
**Forecast target**: daily ridership per station, January–December 2025

Prophet configuration:
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `growth` | `flat` | No long-run trend assumed within the forecast window |
| `yearly_seasonality` | `True` | Captures summer dips, holiday peaks, etc. |
| `weekly_seasonality` | `True` | Captures weekday/weekend patterns |
| `daily_seasonality` | `False` | Data is already aggregated to daily |
| `holidays` | NY state holidays (2024–2025) | Prevents holiday dips from being misread as signal |

### Residual / Lift Calculation

For each station-day in 2025, the model produces:
- `yhat` — predicted ridership (the counterfactual baseline)
- `yhat_lower` / `yhat_upper` — 80% uncertainty interval
- `actual` — observed ridership from MTA data
- `residual` — `actual - yhat` (absolute lift)
- `pct_residual` — `residual / yhat` (percentage lift)

A positive residual means ridership exceeded the model's pre-policy baseline, consistent with riders switching from cars to the subway in response to congestion pricing.

## Analysis (and open avenues)

Analysis of Uplift
- is there uplift in general (by day or month)?
- if there is uplift, is it correlated with distance to congestion pricing locations (e.g. is there higher uplift in ridership for stations that are closer to congestion pricing locations ⭢ this would help establish the possibility of cause and effect)

Improvements
- try to find other covariates so that the Facebook prophet model is better
- is distance of a ride captured? or maybe average distance of ride during a day for each station (it's plausible that stations with further average ride distance is correlated with ridership uplift)


## Files

| File | Contents |
|------|----------|
| `download_nyc_traffic.py` | Downloads MTA hourly ridership data |
| `model.py` | Prophet model: load, fit, predict, residuals |
| `analyze.ipynb` | Analysis and visualization of uplift estimates |
| `explore.ipynb` | Exploratory data analysis |
| `data/nyc_mta_hourly_ridership.csv` | Raw hourly ridership (not tracked in git) |

## Limitations

- The model assumes 2024 trends would have continued into 2025 in the absence of congestion pricing. Any other 2025 shock (e.g., service changes, economic shifts) would be conflated with the policy effect.
- One year of training data is a short window for Prophet; estimates for stations with high week-to-week variance will have wide uncertainty intervals.
- The analysis uses entry counts, not boardings or origin-destination pairs, so it cannot distinguish between new riders and existing riders changing which station they enter at.

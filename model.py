import logging

import holidays as hdays
import pandas as pd
from prophet import Prophet
from tqdm import tqdm

logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

CSV_PATH = "data/nyc_mta_hourly_ridership.csv"
MIN_ANNUAL = 50_000


class RidershipModel:
    def __init__(self):
        self.train = None
        self.test = None
        self.models = {}

    def load_data(self):
        df = pd.read_csv(CSV_PATH, parse_dates=["transit_timestamp"])

        self.train = (
            df[df["transit_timestamp"].dt.year == 2024]
            .assign(date=lambda d: d["transit_timestamp"].dt.normalize())
            .groupby(["date", "station_complex"])["ridership"]
            .sum()
            .reset_index()
        )

        self.test = (
            df[df["transit_timestamp"].dt.year == 2025]
            .assign(date=lambda d: d["transit_timestamp"].dt.normalize())
            .groupby(["date", "station_complex"])["ridership"]
            .sum()
            .reset_index()
        )

    def fit(self):
        valid_stations = (
            self.train.groupby("station_complex")["ridership"]
            .sum()
            .loc[lambda s: s >= MIN_ANNUAL]
            .index.tolist()
        )

        ny_holidays = hdays.country_holidays("US", subdiv="NY", years=[2024, 2025])
        holiday_df = pd.DataFrame([
            {"ds": pd.Timestamp(d), "holiday": name}
            for d, name in ny_holidays.items()
        ])

        ## from exploratory notebook and additional research
        ## we determined that there doesn't appear to be much growth
        ## e.g. population of these areas didn't change significantly
        ## year-to-year numbers didn't change significantly

        self.models = {}
        for station in tqdm(valid_stations, desc="Fitting models"):
            station_df = (
                self.train[self.train["station_complex"] == station]
                .rename(columns={"date": "ds", "ridership": "y"})
            )
            m = Prophet(
                growth="flat",
                holidays=holiday_df,
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
            )
            m.fit(station_df)
            self.models[station] = m

        print(f"Fitted {len(self.models)} models")

    def predict(self):
        future = pd.DataFrame({"ds": pd.date_range("2025-01-01", "2025-12-31")})

        forecasts = []
        for station, m in tqdm(self.models.items(), desc="Generating forecasts"):
            forecast = m.predict(future)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
            forecast["station_complex"] = station
            forecasts.append(forecast)

        forecast_df = pd.concat(forecasts, ignore_index=True)

        results = forecast_df.merge(
            self.test.rename(columns={"date": "ds", "ridership": "actual"}),
            on=["ds", "station_complex"],
            how="left",
        )
        results["residual"] = results["actual"] - results["yhat"]
        results["pct_residual"] = results["residual"] / results["yhat"]

        return results

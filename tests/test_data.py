import pandas as pd
import datetime
from data.historic_handler import HistoricDataHandler


dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

df_vcb = pd.DataFrame({
    "open":   [87_000, 88_000, 87_500, 89_000],
    "high":   [88_500, 89_000, 88_000, 90_000],
    "low":    [86_500, 87_500, 87_000, 88_500],
    "close":  [88_000, 87_500, 89_000, 89_500],
    "volume": [1_200_000, 980_000, 1_500_000, 2_000_000],
}, index=dates)

df_fpt = pd.DataFrame({
    "open":   [120_000, 121_000, 119_500, 122_000],
    "high":   [122_000, 122_500, 121_000, 123_000],
    "low":    [119_500, 120_000, 119_000, 121_500],
    "close":  [121_000, 119_500, 122_000, 122_500],
    "volume": [500_000, 450_000, 600_000, 700_000],
}, index=dates)

data = {"VCB": df_vcb, "FPT": df_fpt}


symbols = ["VCB"]

data = HistoricDataHandler(data,symbols)
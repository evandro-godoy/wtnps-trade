from __future__ import annotations

import pandas as pd

from newapp.plotting import create_dashboard_chart


def build_chart_components(df: pd.DataFrame) -> tuple[str, str]:
    """Build Bokeh script/div from OHLC dataframe."""
    ohlc_data: list[dict[str, float | int | str]] = []
    for ts, row in df.iterrows():
        ohlc_data.append(
            {
                "time": ts.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"])
                if "volume" in row and not pd.isna(row["volume"])
                else 0,
            }
        )

    return create_dashboard_chart(ohlc_data)

"""Regression tests for idempotent AssetsRates persistence."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from newapp.src.database.db import Base
from newapp.src.database.models import AssetsRates
from newapp.src.database.repository import AssetsRatesRepository


def _build_sample_df() -> pd.DataFrame:
    """Create a deterministic OHLCV sample DataFrame."""
    idx = pd.DatetimeIndex(
        [
            datetime(2026, 2, 20, 10, 25, tzinfo=timezone.utc),
            datetime(2026, 2, 20, 10, 30, tzinfo=timezone.utc),
        ]
    )
    return pd.DataFrame(
        {
            "open": [5244.5, 5245.0],
            "high": [5245.0, 5246.0],
            "low": [5239.5, 5240.0],
            "close": [5241.0, 5242.0],
            "tick_volume": [7390, 7410],
            "volume": [34891, 35002],
            "spread": [0, 0],
        },
        index=idx,
    )


def test_save_rates_dataframe_is_idempotent_for_duplicates() -> None:
    """Saving the same candles twice must not violate UNIQUE constraints."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    session = SessionLocal()
    try:
        df = _build_sample_df()

        first_count = AssetsRatesRepository.save_rates_dataframe(
            db=session,
            df=df,
            symbol="WDO$",
            timeframe=300,
            timeframe_str="M5",
            allow_enrich=False,
        )
        second_count = AssetsRatesRepository.save_rates_dataframe(
            db=session,
            df=df,
            symbol="WDO$",
            timeframe=300,
            timeframe_str="M5",
            allow_enrich=False,
        )

        total_rows = session.query(AssetsRates).count()

        assert first_count == 2
        assert second_count == 2
        assert total_rows == 2
    finally:
        session.close()
        engine.dispose()

"""Filesystem access for the seven synthetic banking datasets.

The repository loads each CSV once, caches it in memory, and exposes helpers to
filter slices by zone/quarter/product and serialize them to compact markdown
tables. Per the architecture decision, this layer performs **no analysis** — it
only loads, filters, and serializes so the LLM agents can reason over the data.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import Settings, get_settings
from app.constants import (
    ALL_DATASET_NAMES,
    DATASET_EVENT_LOG,
    DATASET_FILE_NAMES,
)
from app.core.exceptions import DatasetNotFoundError
from app.core.logging import get_logger

_logger = get_logger("dataset_repository")

# Columns used to scope a slice; only applied when present on the frame.
_ZONE_COLUMN: str = "zone"
_QUARTER_COLUMN: str = "quarter"
_PRODUCT_COLUMN: str = "product_type"
_EVENT_DATE_COLUMN: str = "date"


class DatasetRepository:
    """Loads, caches, filters, and serializes the seven banking datasets.

    The repository is constructed once at application startup and shared across
    requests. Loading is lazy and memoized per dataset.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the repository.

        Args:
            settings: Application settings. Defaults to the cached singleton.
        """
        self._settings: Settings = settings or get_settings()
        self._data_dir: Path = self._settings.data_dir
        self._frame_cache: dict[str, pd.DataFrame] = {}

    # -- loading ------------------------------------------------------------

    def load_dataset(self, dataset_name: str) -> pd.DataFrame:
        """Load a single dataset by its identifier, using the in-memory cache.

        Args:
            dataset_name: One of ``constants.ALL_DATASET_NAMES``.

        Returns:
            The dataset as a pandas DataFrame.

        Raises:
            DatasetNotFoundError: If the dataset id is unknown or the CSV file
                is missing from the data directory.
        """
        if dataset_name in self._frame_cache:
            return self._frame_cache[dataset_name]

        file_name = DATASET_FILE_NAMES.get(dataset_name)
        if file_name is None:
            raise DatasetNotFoundError(f"Unknown dataset identifier: '{dataset_name}'.")

        csv_path = self._data_dir / file_name
        if not csv_path.exists():
            raise DatasetNotFoundError(
                f"Dataset file not found: '{csv_path}'. "
                "Run `python scripts/generate_synthetic_data.py` first."
            )

        frame = pd.read_csv(csv_path)
        self._frame_cache[dataset_name] = frame
        _logger.debug("Loaded dataset '%s' with %d rows.", dataset_name, len(frame))
        return frame

    def load_all_datasets(self) -> dict[str, pd.DataFrame]:
        """Eagerly load and cache every dataset.

        Returns:
            A mapping of dataset identifier to its DataFrame.

        Raises:
            DatasetNotFoundError: If any dataset CSV is missing.
        """
        return {name: self.load_dataset(name) for name in ALL_DATASET_NAMES}

    def all_datasets_present(self) -> bool:
        """Check whether every expected CSV exists on disk.

        Returns:
            True when all seven dataset files are present.
        """
        return all(
            (self._data_dir / file_name).exists()
            for file_name in DATASET_FILE_NAMES.values()
        )

    # -- filtering ----------------------------------------------------------

    def filter_dataset_slice(
        self,
        dataset_name: str,
        *,
        zones: list[str] | None = None,
        quarters: list[str] | None = None,
        product: str | None = None,
    ) -> pd.DataFrame:
        """Return a filtered copy of a dataset scoped to the given dimensions.

        Filters are applied only for columns that exist on the dataset, so the
        same call works across heterogeneous schemas.

        Args:
            dataset_name: The dataset identifier to slice.
            zones: Zones to keep; ``None`` keeps all zones.
            quarters: Quarters to keep; ``None`` keeps all quarters.
            product: Product type to keep; ``None`` keeps all products.

        Returns:
            A filtered DataFrame (a copy; the cache is never mutated).
        """
        frame = self.load_dataset(dataset_name)
        sliced = frame

        if zones and _ZONE_COLUMN in sliced.columns:
            sliced = sliced[sliced[_ZONE_COLUMN].isin(zones)]
        if quarters and _QUARTER_COLUMN in sliced.columns:
            sliced = sliced[sliced[_QUARTER_COLUMN].isin(quarters)]
        if product and _PRODUCT_COLUMN in sliced.columns:
            sliced = sliced[sliced[_PRODUCT_COLUMN] == product]

        return sliced.copy()

    # -- serialization ------------------------------------------------------

    def serialize_dataset_slice_to_markdown(
        self,
        dataset_name: str,
        *,
        zones: list[str] | None = None,
        quarters: list[str] | None = None,
        product: str | None = None,
        max_rows: int = 200,
    ) -> str:
        """Serialize a filtered dataset slice to a compact markdown table.

        Args:
            dataset_name: The dataset identifier to serialize.
            zones: Zones to keep; ``None`` keeps all.
            quarters: Quarters to keep; ``None`` keeps all.
            product: Product type to keep; ``None`` keeps all.
            max_rows: Safety cap on rows included in the serialized table.

        Returns:
            A markdown table string (with a heading), or a "no rows" note when
            the slice is empty.
        """
        sliced = self.filter_dataset_slice(
            dataset_name, zones=zones, quarters=quarters, product=product
        )
        heading = f"### Dataset: {dataset_name}"
        if sliced.empty:
            return f"{heading}\n(No matching rows.)"

        truncated = sliced.head(max_rows)
        table = truncated.to_markdown(index=False)
        suffix = (
            f"\n(Showing {max_rows} of {len(sliced)} rows.)"
            if len(sliced) > max_rows
            else ""
        )
        return f"{heading}\n{table}{suffix}"

    def serialize_datasets_for_analysis(
        self,
        dataset_names: list[str],
        *,
        zones: list[str] | None = None,
        quarters: list[str] | None = None,
    ) -> str:
        """Serialize several datasets into a single markdown context block.

        The event log is intentionally never quarter-filtered (its rows are
        dated, not quartered) so the analyst always sees the full event history
        for the scoped zones — the triggering event must be in context.

        Args:
            dataset_names: Datasets to include, in order.
            zones: Zones to keep across all datasets; ``None`` keeps all.
            quarters: Quarters to keep (ignored for the event log).

        Returns:
            A newline-separated markdown document covering all requested
            datasets.
        """
        blocks: list[str] = []
        for dataset_name in dataset_names:
            applied_quarters = None if dataset_name == DATASET_EVENT_LOG else quarters
            blocks.append(
                self.serialize_dataset_slice_to_markdown(
                    dataset_name, zones=zones, quarters=applied_quarters
                )
            )
        return "\n\n".join(blocks)

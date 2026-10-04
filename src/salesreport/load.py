"""Read the config and every source file into one table with standard column names."""

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

STANDARD_COLUMNS = ["order_id", "date", "sku", "product", "quantity", "unit_price"]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    """One export format: which files, how to read them and what the columns are called."""

    name: str
    pattern: str
    currency: str
    date_format: str
    columns: dict[str, str]
    decimal: str = "."
    read: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    currency: str
    sources: list[Source]


def load_config(path: Path) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    sources = [Source(**s) for s in data["source"]]
    for source in sources:
        missing = set(STANDARD_COLUMNS) - source.columns.keys()
        if missing:
            raise ValueError(f"source {source.name!r}: no column mapping for {sorted(missing)}")
    return Config(currency=data["report"]["currency"], sources=sources)


def read_source(source: Source, folder: Path) -> pd.DataFrame:
    """All files of one source, as text, plus the file name and row number each line came from."""
    files = sorted(folder.glob(source.pattern))
    if not files:
        log.warning("%s: no files match %s in %s", source.name, source.pattern, folder)
        return pd.DataFrame(columns=[*STANDARD_COLUMNS, "source_file", "source_row"])
    return pd.concat([_read_file(path, source) for path in files], ignore_index=True)


def _read_file(path: Path, source: Source) -> pd.DataFrame:
    options = {"dtype": str, **source.read}
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path, **options)
    else:
        raw = pd.read_csv(path, skip_blank_lines=False, **options)

    renamed = raw.rename(columns={theirs: ours for ours, theirs in source.columns.items()})
    missing = [source.columns[c] for c in STANDARD_COLUMNS if c not in renamed.columns]
    if missing:
        raise ValueError(f"{path.name}: expected columns {missing} not found")

    frame = renamed[STANDARD_COLUMNS].copy()
    # Row number as the user sees it in Excel or a text editor: header row + rows skipped above it
    frame["source_row"] = raw.index + 2 + source.read.get("skiprows", 0)
    frame["source_file"] = path.name
    blank = frame[STANDARD_COLUMNS].isna().all(axis=1)
    log.info("%s: %s rows from %s", source.name, (~blank).sum(), path.name)
    return frame[~blank]

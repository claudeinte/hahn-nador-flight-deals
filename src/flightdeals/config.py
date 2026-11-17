"""Lädt config.toml und stellt Hilfsfunktionen für Zeit und Pfade bereit."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    raw: dict
    root: Path

    def __getitem__(self, key):
        return self.raw[key]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.raw["page"]["timezone"])

    @property
    def route_out(self) -> str:
        r = self.raw["route"]
        return f"{r['origin']}-{r['destination']}"

    @property
    def route_ret(self) -> str:
        r = self.raw["route"]
        return f"{r['destination']}-{r['origin']}"

    @property
    def data_dir(self) -> Path:
        return Path(os.environ.get("FLIGHTDEALS_DATA_DIR", self.root / "data"))

    @property
    def output_dir(self) -> Path:
        return Path(os.environ.get("FLIGHTDEALS_OUTPUT_DIR", self.root / "output"))

    @property
    def fonts_dir(self) -> Path:
        return self.root / "assets" / "fonts"

    def now(self) -> datetime:
        """Aktuelle Zeit in Europe/Berlin. Für Tests über FLIGHTDEALS_NOW (ISO) überschreibbar."""
        override = os.environ.get("FLIGHTDEALS_NOW")
        if override:
            dt = datetime.fromisoformat(override)
            return dt.astimezone(self.tz) if dt.tzinfo else dt.replace(tzinfo=self.tz)
        return datetime.now(self.tz)

    def city(self, code: str) -> str:
        r = self.raw["route"]
        return {r["origin"]: r["origin_name"], r["destination"]: r["destination_name"]}.get(code, code)


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path) if path else ROOT / "config.toml"
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return Config(raw=raw, root=path.parent)

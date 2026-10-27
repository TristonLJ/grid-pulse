"""Client for the Ember electricity data API (https://api.ember-energy.org)."""

import os

import requests

BASE_URL = "https://api.ember-energy.org/v1"


def fetch(endpoint: str, api_key: str | None = None, **params) -> list[dict]:
    api_key = api_key or os.environ.get("EMBER_API_KEY")
    if not api_key:
        raise RuntimeError("EMBER_API_KEY is not set. Copy .env.example to .env and add your key.")
    resp = requests.get(f"{BASE_URL}/{endpoint}", params={**params, "api_key": api_key}, timeout=60)
    resp.raise_for_status()
    return resp.json()["data"]


def generation_monthly(entity_code: str = "ZAF", start_date: str = "2015-01", api_key: str | None = None) -> list[dict]:
    """Monthly generation by fuel type (TWh and % share)."""
    return fetch("electricity-generation/monthly", api_key, entity_code=entity_code, start_date=start_date)


def demand_monthly(entity_code: str = "ZAF", start_date: str = "2015-01", api_key: str | None = None) -> list[dict]:
    """Monthly total electricity demand (TWh)."""
    return fetch("electricity-demand/monthly", api_key, entity_code=entity_code, start_date=start_date)


def yearly(dataset: str, codes: list[str], regions: list[str], start_date: str = "2000") -> list[dict]:
    """A yearly dataset for several countries (ISO-3 codes) plus regional aggregates (by name).

    Ember filters countries by `entity_code` but aggregates like "World" only by `entity`,
    so this makes one request for each and combines them.
    """
    countries = fetch(f"{dataset}/yearly", entity_code=",".join(codes), start_date=start_date)
    aggregates = fetch(f"{dataset}/yearly", entity=",".join(regions), start_date=start_date)
    return countries + aggregates

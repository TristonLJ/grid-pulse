"""Client for the Ember electricity data API (https://api.ember-energy.org)."""

import os

import requests

BASE_URL = "https://api.ember-energy.org/v1"


def _get(endpoint: str, params: dict, api_key: str | None = None) -> list[dict]:
    api_key = api_key or os.environ.get("EMBER_API_KEY")
    if not api_key:
        raise RuntimeError("EMBER_API_KEY is not set. Copy .env.example to .env and add your key.")
    resp = requests.get(f"{BASE_URL}/{endpoint}", params={**params, "api_key": api_key}, timeout=60)
    resp.raise_for_status()
    return resp.json()["data"]


def generation_monthly(entity_code: str = "ZAF", start_date: str = "2015-01", api_key: str | None = None) -> list[dict]:
    """Monthly generation by fuel type (TWh and % share)."""
    return _get("electricity-generation/monthly", {"entity_code": entity_code, "start_date": start_date}, api_key)


def demand_monthly(entity_code: str = "ZAF", start_date: str = "2015-01", api_key: str | None = None) -> list[dict]:
    """Monthly total electricity demand (TWh)."""
    return _get("electricity-demand/monthly", {"entity_code": entity_code, "start_date": start_date}, api_key)

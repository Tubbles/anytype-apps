"""Thin wrapper around the Anytype local HTTP API."""

import os
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("ANYTYPE_API_URL", "http://127.0.0.1:31012")
API_KEY = os.environ["ANYTYPE_API_KEY"]
API_VERSION = "2025-05-21"

# Rate limiting: 1 req/sec sustained, burst of 60
_last_request_time = 0.0


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Anytype-Version": API_VERSION,
        "Content-Type": "application/json",
    }


def _rate_limit():
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_request_time = time.monotonic()


def get(path: str) -> dict:
    _rate_limit()
    r = requests.get(f"{API_URL}/v1{path}", headers=_headers())
    r.raise_for_status()
    return r.json()


def post(path: str, body: dict | None = None) -> dict:
    _rate_limit()
    r = requests.post(f"{API_URL}/v1{path}", headers=_headers(), json=body or {})
    r.raise_for_status()
    return r.json()


def post_raw(path: str, body: dict | None = None) -> bytes:
    """POST that returns raw bytes (for export endpoints)."""
    _rate_limit()
    r = requests.post(f"{API_URL}/v1{path}", headers=_headers(), json=body or {})
    r.raise_for_status()
    return r.content


def list_spaces() -> list[dict]:
    return get("/spaces")["data"]


def search_objects(space_id: str, query: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
    """Search objects in a space. Returns all objects when query is empty."""
    all_objects = []
    while True:
        result = post(f"/spaces/{space_id}/search", {
            "query": query,
            "limit": limit,
            "offset": offset,
        })
        all_objects.extend(result["data"])
        if not result["pagination"]["has_more"]:
            break
        offset += limit
    return all_objects


def get_object(space_id: str, object_id: str) -> dict:
    return get(f"/spaces/{space_id}/objects/{object_id}")


def export_object_markdown(space_id: str, object_id: str) -> bytes:
    return post_raw(f"/spaces/{space_id}/objects/{object_id}/export/markdown")


def list_types(space_id: str) -> list[dict]:
    result = get(f"/spaces/{space_id}/types")
    return result["data"]


def list_properties(space_id: str) -> list[dict]:
    result = get(f"/spaces/{space_id}/properties")
    return result["data"]


def create_object(space_id: str, type_key: str, name: str, **kwargs) -> dict:
    body = {"type_key": type_key, "name": name, **kwargs}
    return post(f"/spaces/{space_id}/objects", body)


def create_type(space_id: str, name: str, key: str, **kwargs) -> dict:
    body = {"name": name, "key": key, **kwargs}
    return post(f"/spaces/{space_id}/types", body)


def create_property(space_id: str, name: str, key: str, format: str, **kwargs) -> dict:
    body = {"name": name, "key": key, "format": format, **kwargs}
    return post(f"/spaces/{space_id}/properties", body)

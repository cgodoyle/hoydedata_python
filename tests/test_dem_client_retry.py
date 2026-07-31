import asyncio

import httpx
import numpy as np
import pytest

from hoydedata_python import dem_client
from hoydedata_python.config import settings


def test_fetch_elevation_data_uses_settings_timeout_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_get(self: httpx.AsyncClient, url: str, params: dict, timeout: int | float) -> httpx.Response:
        captured["timeout"] = timeout
        request = httpx.Request("GET", url)
        return httpx.Response(200, content=b"tiff-bytes", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    content = asyncio.run(
        dem_client.fetch_elevation_data((0.0, 0.0, 10.0, 10.0), retry_min_wait=0, retry_max_wait=0)
    )

    assert content == b"tiff-bytes"
    assert captured["timeout"] == settings.API_TIMEOUT


def test_fetch_elevation_data_passes_per_call_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_get(self: httpx.AsyncClient, url: str, params: dict, timeout: int | float) -> httpx.Response:
        captured["timeout"] = timeout
        request = httpx.Request("GET", url)
        return httpx.Response(200, content=b"tiff-bytes", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    asyncio.run(
        dem_client.fetch_elevation_data(
            (0.0, 0.0, 10.0, 10.0),
            timeout_seconds=8,
            retry_attempts=1,
            retry_min_wait=0,
            retry_max_wait=0,
        )
    )

    assert captured["timeout"] == 8


def test_fetch_elevation_data_retry_attempts_controls_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_get(self: httpx.AsyncClient, url: str, params: dict, timeout: int | float) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("connection timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(httpx.ConnectTimeout):
        asyncio.run(
            dem_client.fetch_elevation_data(
                (0.0, 0.0, 10.0, 10.0),
                retry_attempts=1,
                retry_min_wait=0,
                retry_max_wait=0,
            )
        )

    assert calls == 1

    calls = 0
    with pytest.raises(httpx.ConnectTimeout):
        asyncio.run(
            dem_client.fetch_elevation_data(
                (0.0, 0.0, 10.0, 10.0),
                retry_attempts=3,
                retry_min_wait=0,
                retry_max_wait=0,
            )
        )

    assert calls == 3


def test_fetch_elevation_data_retries_selected_http_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_get(self: httpx.AsyncClient, url: str, params: dict, timeout: int | float) -> httpx.Response:
        nonlocal calls
        calls += 1
        request = httpx.Request("GET", url)
        return httpx.Response(503, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            dem_client.fetch_elevation_data(
                (0.0, 0.0, 10.0, 10.0),
                retry_attempts=3,
                retry_min_wait=0,
                retry_max_wait=0,
            )
        )

    assert calls == 3


def test_fetch_elevation_data_does_not_retry_client_http_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_get(self: httpx.AsyncClient, url: str, params: dict, timeout: int | float) -> httpx.Response:
        nonlocal calls
        calls += 1
        request = httpx.Request("GET", url)
        return httpx.Response(404, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            dem_client.fetch_elevation_data(
                (0.0, 0.0, 10.0, 10.0),
                retry_attempts=3,
                retry_min_wait=0,
                retry_max_wait=0,
            )
        )

    assert calls == 1


def test_download_and_extract_forwards_request_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_fetch_elevation_data(
        bounds: tuple,
        resolution_meters: float = 5,
        timeout_seconds: int | float | None = None,
        retry_attempts: int | None = None,
        retry_min_wait: int | float | None = None,
        retry_max_wait: int | float | None = None,
    ) -> bytes:
        captured.update(
            {
                "bounds": bounds,
                "resolution_meters": resolution_meters,
                "timeout_seconds": timeout_seconds,
                "retry_attempts": retry_attempts,
                "retry_min_wait": retry_min_wait,
                "retry_max_wait": retry_max_wait,
            }
        )
        return b"tiff-bytes"

    def fake_convert_tiff_bytes_to_raster(tiff_bytes: bytes) -> tuple[np.ndarray, dict]:
        assert tiff_bytes == b"tiff-bytes"
        elevation_array = np.array([[123.0]])
        raster_profile = {"transform": dem_client.rasterio.transform.from_origin(-10, 10, 20, 20)}
        return elevation_array, raster_profile

    monkeypatch.setattr(dem_client, "fetch_elevation_data", fake_fetch_elevation_data)
    monkeypatch.setattr(dem_client, "convert_tiff_bytes_to_raster", fake_convert_tiff_bytes_to_raster)

    result = asyncio.run(
        dem_client.download_and_extract_elevation_values_for_points(
            np.array([0.0, 0.0]),
            resolution_meters=5,
            timeout_seconds=8,
            retry_attempts=1,
            retry_min_wait=0,
            retry_max_wait=0,
        )
    )

    assert result.tolist() == [123.0]
    assert captured["timeout_seconds"] == 8
    assert captured["retry_attempts"] == 1
    assert captured["retry_min_wait"] == 0
    assert captured["retry_max_wait"] == 0

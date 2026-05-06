import asyncio
from pathlib import Path

import pytest
from shapely.geometry import box

from hoydedata_python import dem_client
from hoydedata_python import export_client


@pytest.mark.smoke
def test_download_elevation_model_output_naming(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, tuple, float]] = []

    async def fake_fetch_and_save(output_filename: Path, bounds: tuple, resolution_meters: float) -> None:
        calls.append((Path(output_filename), bounds, resolution_meters))

    monkeypatch.setattr(dem_client, "fetch_and_save_elevation_tile", fake_fetch_and_save)

    bounds = (0.0, 0.0, 100.0, 100.0)

    explicit_file = tmp_path / "custom.tif"
    asyncio.run(dem_client.download_elevation_model(bounds=bounds, resolution_meters=10, output_path=explicit_file))

    output_dir = tmp_path / "dem_out"
    asyncio.run(dem_client.download_elevation_model(bounds=bounds, resolution_meters=10, output_path=output_dir))

    assert calls[0][0] == explicit_file
    assert calls[1][0] == output_dir / "dem_ndh_10m.tif"


@pytest.mark.smoke
def test_send_export_job_payload_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyResponse:
        def json(self) -> dict[str, object]:
            return {"JobID": 123}

    def fake_get(url: str, params: dict[str, str]) -> DummyResponse:
        captured["url"] = url
        captured["params"] = params
        return DummyResponse()

    monkeypatch.setattr(export_client.requests, "get", fake_get)

    polygon = export_client.gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10)], crs=25833)

    response = export_client.send_export_job(
        projects_name=["PROJECT_A", "PROJECT_B"],
        polygon=polygon,
        username="user",
        password="pass",
        kartblad=2000,
        crs=25833,
        email="you@example.com",
        name="smoke-test",
    )

    assert response["JobID"] == 123

    request_payload = captured["params"]
    assert isinstance(request_payload, dict)
    request_json = request_payload["request"]
    assert isinstance(request_json, str)
    assert "PROJECT_A,PROJECT_B" in request_json
    assert '"MapsheetSize": 2000' in request_json
    assert '"InputWkid": 25833' in request_json

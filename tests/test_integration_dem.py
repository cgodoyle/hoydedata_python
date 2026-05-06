import asyncio

import numpy as np
import pytest
import rasterio

from hoydedata_python.config import settings
from hoydedata_python.dem_client import download_elevation_model


@pytest.mark.integration
def test_download_elevation_model_real_service(tmp_path) -> None:
    bounds = (251091.9498, 7032567.1219, 265107.0872, 7042621.2324)
    output_path = tmp_path / "dem_real.tif"

    asyncio.run(
        download_elevation_model(
            bounds=bounds,
            resolution_meters=10,
            output_path=output_path,
        )
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    with rasterio.open(output_path) as dataset:
        assert dataset.driver == "GTiff"
        assert dataset.count == 1
        assert dataset.width > 0
        assert dataset.height > 0

        assert dataset.crs is not None
        assert dataset.crs.to_epsg() == settings.DEFAULT_CRS

        x_res, y_res = dataset.res
        assert abs(x_res - 10.0) < 1.0
        assert abs(y_res - 10.0) < 1.0

        transform_values = np.array(dataset.transform)[:6]
        assert np.isfinite(transform_values).all()

        raster_bounds = dataset.bounds
        assert raster_bounds.left < raster_bounds.right
        assert raster_bounds.bottom < raster_bounds.top

        req_left, req_bottom, req_right, req_top = bounds
        intersects_requested_bbox = not (
            raster_bounds.right <= req_left
            or raster_bounds.left >= req_right
            or raster_bounds.top <= req_bottom
            or raster_bounds.bottom >= req_top
        )
        assert intersects_requested_bbox

        band_1 = dataset.read(1, masked=True)
        finite_mask = np.isfinite(np.ma.filled(band_1.astype(float), np.nan))
        valid_ratio = float(finite_mask.mean())
        assert valid_ratio > 0.01

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))
from hoydedata_python import dem_client


def main():
    bounds = [251091.9498, 7032567.1219, 265107.0872, 7042621.2324]
    asyncio.run(dem_client.download_elevation_model(bounds=bounds, resolution_meters=10, output_path="dem.tif"))


if __name__ == "__main__":
    main()

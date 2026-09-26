"""
download_live_cmems.py
----------------------
Downloads live Copernicus Marine (CMEMS) hourly ocean currents and wave data
for the MV Rubymar incident in the Southern Red Sea / Bab-el-Mandeb.
"""

import os
import sys
from pathlib import Path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from datetime import datetime
from src.data_fetcher import EnvironmentalDataManager

def main():
    print("=" * 70)
    print("DOWNLOADING LIVE DATA FROM COPERNICUS MARINE SERVICE (CMEMS)")
    print("=" * 70)

    mgr = EnvironmentalDataManager(data_root="data")
    username, password = mgr.get_credentials()
    print(f" -> Authenticating as user: {username}")

    # Bounding box covering Bab-el-Mandeb & Hanish Islands (Southern Red Sea)
    min_lon = 41.5
    max_lon = 44.0
    min_lat = 12.5
    max_lat = 15.0

    # 72-hour window leading up to Rubymar sinking (March 2, 2024)
    start_dt = datetime(2024, 2, 27, 0, 0)
    end_dt = datetime(2024, 3, 2, 12, 0)

    print(f" -> Region: Lon [{min_lon}, {max_lon}], Lat [{min_lat}, {max_lat}]")
    print(f" -> Time Window: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')} UTC")

    # 1. Download Currents
    print("\n[STEP 1] Fetching Hourly Surface Currents (uo, vo)...")
    try:
        curr_path = mgr.download_cmems_currents(
            min_lon=min_lon,
            max_lon=max_lon,
            min_lat=min_lat,
            max_lat=max_lat,
            start_time=start_dt,
            end_time=end_dt,
            output_filename="cmems_currents_rubymar.nc"
        )
        print(f" -> Successfully downloaded: {curr_path} ({curr_path.stat().st_size / 1024:.1f} KB) [OK]")
    except Exception as e:
        print(f" -> ERROR downloading currents: {e}")

    # 2. Download Wave Stokes Drift
    print("\n[STEP 2] Fetching Wave Stokes Drift (VSDX, VSDY, VHM0)...")
    try:
        wave_path = mgr.download_cmems_waves(
            min_lon=min_lon,
            max_lon=max_lon,
            min_lat=min_lat,
            max_lat=max_lat,
            start_time=start_dt,
            end_time=end_dt,
            output_filename="cmems_waves_rubymar.nc"
        )
        print(f" -> Successfully downloaded: {wave_path} ({wave_path.stat().st_size / 1024:.1f} KB) [OK]")
    except Exception as e:
        print(f" -> ERROR downloading waves: {e}")

    # 3. Download 10m Wind Fields
    print("\n[STEP 3] Fetching Hourly 10m Wind Fields (u10, v10)...")
    try:
        wind_path = mgr.download_cmems_wind(
            min_lon=min_lon,
            max_lon=max_lon,
            min_lat=min_lat,
            max_lat=max_lat,
            start_time=start_dt,
            end_time=end_dt,
            output_filename="cmems_wind_rubymar.nc"
        )
        print(f" -> Successfully downloaded: {wind_path} ({wind_path.stat().st_size / 1024:.1f} KB) [OK]")
    except Exception as e:
        print(f" -> ERROR downloading wind: {e}")

    print("\n" + "=" * 70)
    print("CMEMS DOWNLOAD PROCESS FINISHED")
    print("=" * 70)

if __name__ == "__main__":
    main()

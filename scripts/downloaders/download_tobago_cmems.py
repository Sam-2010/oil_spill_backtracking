"""
download_tobago_cmems.py
------------------------
Downloads live Copernicus Marine (CMEMS) hourly ocean currents, winds, and waves
for the Tobago oil spill (barge Gulfstream) in the Southern Caribbean.
"""

from datetime import datetime
from src.data_fetcher import EnvironmentalDataManager

def main():
    print("=" * 70)
    print("DOWNLOADING CMEMS DATA FOR TOBAGO OIL SPILL (FEB 2024)")
    print("=" * 70)

    mgr = EnvironmentalDataManager(data_root="data")
    username, password = mgr.get_credentials()
    print(f" -> Authenticating as user: {username}")

    # Bounding box covering Tobago, Trinidad, and Grenada channel
    min_lon = -62.0
    max_lon = -60.0
    min_lat = 10.5
    max_lat = 12.0

    # 36-hour window covering Feb 7 (grounding) to Feb 8 (satellite detection)
    start_dt = datetime(2024, 2, 7, 0, 0)
    end_dt = datetime(2024, 2, 8, 12, 0)

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
            output_filename="cmems_currents_tobago.nc"
        )
        print(f" -> Downloaded: {curr_path} ({curr_path.stat().st_size / 1024:.1f} KB) [OK]")
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
            output_filename="cmems_waves_tobago.nc"
        )
        print(f" -> Downloaded: {wave_path} ({wave_path.stat().st_size / 1024:.1f} KB) [OK]")
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
            output_filename="cmems_wind_tobago.nc"
        )
        print(f" -> Downloaded: {wind_path} ({wind_path.stat().st_size / 1024:.1f} KB) [OK]")
    except Exception as e:
        print(f" -> ERROR downloading wind: {e}")

    print("\n" + "=" * 70)
    print("TOBAGO DATA DOWNLOAD COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()

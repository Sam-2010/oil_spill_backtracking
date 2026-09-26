"""
download_new_benchmarks.py
--------------------------
Downloads live Copernicus Marine (CMEMS) data for:
1. Manila Bay Tanker Sinking (MT Terra Nova, July 2024)
2. Red Sea Tanker Strike (MV Sounion, August 2024)
"""

from datetime import datetime
from src.data_fetcher import EnvironmentalDataManager

def main():
    print("=" * 70)
    print("DOWNLOADING CMEMS DATA FOR MANILA BAY & RED SEA SOUNION INCIDENTS")
    print("=" * 70)

    mgr = EnvironmentalDataManager(data_root="data")
    username, password = mgr.get_credentials()
    print(f" -> Authenticating as user: {username}")

    # =========================================================================
    # PART 1: Manila Bay (MT Terra Nova, July 2024)
    # =========================================================================
    print("\n" + "=" * 50)
    print("[1/2] FETCHING DATA FOR MANILA BAY (MT TERRA NOVA)")
    print("=" * 50)
    m_min_lon, m_max_lon = 120.3, 121.2
    m_min_lat, m_max_lat = 14.1, 14.9
    m_start = datetime(2024, 7, 24, 0, 0)
    m_end = datetime(2024, 7, 26, 14, 0)

    try:
        mgr.download_cmems_currents(
            min_lon=m_min_lon, max_lon=m_max_lon,
            min_lat=m_min_lat, max_lat=m_max_lat,
            start_time=m_start, end_time=m_end,
            output_filename="cmems_currents_manila.nc"
        )
        mgr.download_cmems_waves(
            min_lon=m_min_lon, max_lon=m_max_lon,
            min_lat=m_min_lat, max_lat=m_max_lat,
            start_time=m_start, end_time=m_end,
            output_filename="cmems_waves_manila.nc"
        )
        mgr.download_cmems_wind(
            min_lon=m_min_lon, max_lon=m_max_lon,
            min_lat=m_min_lat, max_lat=m_max_lat,
            start_time=m_start, end_time=m_end,
            output_filename="cmems_wind_manila.nc"
        )
        print(" -> Manila Bay data downloaded successfully [OK]")
    except Exception as e:
        print(f" -> ERROR in Manila Bay download: {e}")

    # =========================================================================
    # PART 2: Red Sea MV Sounion (August 2024)
    # =========================================================================
    print("\n" + "=" * 50)
    print("[2/2] FETCHING DATA FOR RED SEA (MV SOUNION)")
    print("=" * 50)
    s_min_lon, s_max_lon = 41.0, 43.0
    s_min_lat, s_max_lat = 14.0, 16.5
    s_start = datetime(2024, 8, 21, 0, 0)
    s_end = datetime(2024, 8, 23, 14, 0)

    try:
        mgr.download_cmems_currents(
            min_lon=s_min_lon, max_lon=s_max_lon,
            min_lat=s_min_lat, max_lat=s_max_lat,
            start_time=s_start, end_time=s_end,
            output_filename="cmems_currents_sounion.nc"
        )
        mgr.download_cmems_waves(
            min_lon=s_min_lon, max_lon=s_max_lon,
            min_lat=s_min_lat, max_lat=s_max_lat,
            start_time=s_start, end_time=s_end,
            output_filename="cmems_waves_sounion.nc"
        )
        mgr.download_cmems_wind(
            min_lon=s_min_lon, max_lon=s_max_lon,
            min_lat=s_min_lat, max_lat=s_max_lat,
            start_time=s_start, end_time=s_end,
            output_filename="cmems_wind_sounion.nc"
        )
        print(" -> MV Sounion data downloaded successfully [OK]")
    except Exception as e:
        print(f" -> ERROR in Sounion download: {e}")

    print("\n" + "=" * 70)
    print("ALL NEW BENCHMARK DATA DOWNLOADED")
    print("=" * 70)

if __name__ == "__main__":
    main()

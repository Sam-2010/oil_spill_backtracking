"""
download_mc20_pipeline.py
-------------------------
Downloads all authentic datasets for the Taylor Energy MC-20 incident (Nov 17, 2023):
1. CMEMS Hourly Ocean Currents (uo, vo)
2. CMEMS Hourly Blended Scatterometer Winds (eastward_wind, northward_wind)
3. CMEMS Hourly Wave Stokes Drift (VSDX, VSDY)
4. NOAA Marine Cadastre Raw AIS Archive (AIS_2023_11_17.zip)
   - Streamed via chunked HTTP range requests
   - Filtered for the Mississippi Canyon sector (Lat: [28.5, 29.3], Lon: [-89.5, -88.6])
"""

import os
import sys
from pathlib import Path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

import io
import csv
import zipfile
import urllib.request
from datetime import datetime

from src.data_fetcher import EnvironmentalDataManager

def download_cmems():
    print("=" * 65)
    print("STEP 1: FETCHING COPERNICUS MARINE (CMEMS) DATA FOR MC-20")
    print("=" * 65)

    mgr = EnvironmentalDataManager(data_root="data")
    username, password = mgr.get_credentials()
    print(f" -> Authenticated with Copernicus Marine as: {username}")

    # Bounding box around Mississippi Canyon Block 20 & Mississippi River delta approaches
    min_lon, max_lon = -89.6, -88.6
    min_lat, max_lat = 28.5, 29.4

    # 48-hour window covering Nov 16 00:00 to Nov 18 04:00 UTC
    start_time = datetime(2023, 11, 16, 0, 0)
    end_time = datetime(2023, 11, 18, 4, 0)

    print(f" -> Domain: Lon [{min_lon}, {max_lon}], Lat [{min_lat}, {max_lat}]")
    print(f" -> Timeframe: {start_time} to {end_time} UTC")

    # 1. Currents
    mgr.download_cmems_currents(
        min_lon=min_lon, max_lon=max_lon,
        min_lat=min_lat, max_lat=max_lat,
        start_time=start_time, end_time=end_time,
        output_filename="cmems_currents_mc20.nc"
    )

    # 2. Waves
    mgr.download_cmems_waves(
        min_lon=min_lon, max_lon=max_lon,
        min_lat=min_lat, max_lat=max_lat,
        start_time=start_time, end_time=end_time,
        output_filename="cmems_waves_mc20.nc"
    )

    # 3. Wind
    mgr.download_cmems_wind(
        min_lon=min_lon, max_lon=max_lon,
        min_lat=min_lat, max_lat=max_lat,
        start_time=start_time, end_time=end_time,
        output_filename="cmems_wind_mc20.nc"
    )
    print(" -> All CMEMS NetCDFs for MC-20 successfully downloaded! [OK]")

def download_noaa_ais():
    print("\n" + "=" * 65)
    print("STEP 2: DOWNLOADING NOAA AIS BROADCASTS FOR NOV 17, 2023")
    print("=" * 65)

    noaa_url = "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/AIS_2023_11_17.zip"
    ais_dir = Path("data/ais")
    ais_dir.mkdir(parents=True, exist_ok=True)
    target_zip = ais_dir / "AIS_2023_11_17.zip"
    output_csv = ais_dir / "taylor_energy_mc20_noaa_ais_2023_11_17.csv"

    min_lat, max_lat = 28.5, 29.4
    min_lon, max_lon = -89.6, -88.6

    # Download with range chunks if not already downloaded
    total_size = 308726359 # ~294 MB
    chunk_size = 12 * 1024 * 1024

    current_size = target_zip.stat().st_size if target_zip.exists() else 0

    if current_size < 300000000:
        print(f" -> Downloading NOAA AIS archive ({total_size / (1024*1024):.1f} MB)...")
        while current_size < total_size:
            start_byte = current_size
            end_byte = min(current_size + chunk_size - 1, total_size - 1)
            expected = end_byte - start_byte + 1

            success = False
            for attempt in range(1, 10):
                try:
                    req = urllib.request.Request(
                        noaa_url,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                            'Range': f'bytes={start_byte}-{end_byte}'
                        }
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = resp.read()
                        with open(target_zip, 'ab' if start_byte > 0 else 'wb') as f:
                            f.write(data)
                        current_size += len(data)
                        pct = (current_size / total_size) * 100
                        print(f"    Downloaded: {current_size / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({pct:.1f}%)")
                        success = True
                        break
                except Exception as e:
                    import time
                    print(f"    [Retry {attempt}] Chunk error: {e}. Retrying in 2s...")
                    time.sleep(2)
            if not success:
                raise RuntimeError("Failed downloading NOAA AIS archive.")
        print(" -> Download complete!")
    else:
        print(f" -> Archive already present: {target_zip} ({current_size / (1024*1024):.1f} MB)")

    # Filter records
    print("\nFiltering AIS broadcasts for Mississippi Canyon Block 20...")
    matched_records = 0
    unique_vessels = {}

    with zipfile.ZipFile(target_zip, 'r') as z:
        csv_filename = [n for n in z.namelist() if n.lower().endswith('.csv')][0]
        print(f" -> Streaming from: {csv_filename}")

        with z.open(csv_filename, 'r') as f_in, open(output_csv, 'w', newline='', encoding='utf-8') as f_out:
            reader = csv.DictReader(io.TextIOWrapper(f_in, encoding='utf-8'))
            fieldnames = [
                "timestamp", "mmsi", "imo", "vessel_name", "vessel_type",
                "callsign", "latitude", "longitude", "speed_knots", "course_deg", "nav_status", "draft"
            ]
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            for i, row in enumerate(reader):
                if i % 1000000 == 0 and i > 0:
                    print(f"    ... processed {i:,} global US pings, found {matched_records:,} matches in MC-20 sector")

                try:
                    lat = float(row.get('LAT', 0.0))
                    lon = float(row.get('LON', 0.0))
                except (ValueError, TypeError):
                    continue

                if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                    mmsi = row.get('MMSI', '').strip()
                    vessel_name = row.get('VesselName', '').strip()
                    imo = row.get('IMO', '').strip()
                    vtype = row.get('VesselType', '').strip()
                    callsign = row.get('CallSign', '').strip()
                    sog = row.get('SOG', '').strip()
                    cog = row.get('COG', '').strip()
                    status = row.get('Status', '').strip()
                    draft = row.get('Draft', '').strip()
                    base_datetime = row.get('BaseDateTime', '').strip()

                    writer.writerow({
                        "timestamp": base_datetime,
                        "mmsi": mmsi,
                        "imo": imo,
                        "vessel_name": vessel_name,
                        "vessel_type": vtype,
                        "callsign": callsign,
                        "latitude": lat,
                        "longitude": lon,
                        "speed_knots": sog,
                        "course_deg": cog,
                        "nav_status": status,
                        "draft": draft
                    })
                    matched_records += 1
                    if mmsi not in unique_vessels:
                        unique_vessels[mmsi] = {"name": vessel_name, "type": vtype, "imo": imo, "pings": 0}
                    unique_vessels[mmsi]["pings"] += 1

    print("\n" + "=" * 65)
    print("NOAA AIS EXTRACTION FOR MC-20 COMPLETE!")
    print(f" -> Output CSV: {output_csv} ({output_csv.stat().st_size / (1024*1024):.2f} MB)")
    print(f" -> Total sector pings: {matched_records:,}")
    print(f" -> Distinct vessels in MC-20 sector: {len(unique_vessels)}")
    print("=" * 65)

if __name__ == "__main__":
    download_cmems()
    download_noaa_ais()

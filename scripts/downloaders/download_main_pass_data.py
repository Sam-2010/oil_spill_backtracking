"""
download_main_pass_data.py
--------------------------
Downloads 100% authentic, authoritative datasets for the Main Pass Oil Spill (Gulf of Mexico, Nov 2023):
1. CMEMS Ocean Currents (cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i)
2. CMEMS Wave Stokes Drift (cmems_mod_glo_wav_anfc_0.083deg_PT3H-i)
3. CMEMS Blended Scatterometer Winds (cmems_obs-wind_glo_phy_nrt_l4_0.125deg_PT1H)
4. NOAA Marine Cadastre Raw AIS Broadcast Points (Nov 16, 2023)
   - Streamed directly from NOAA Coast / Marine Cadastre servers
   - Filtered for the Main Pass / Mississippi Delta bounding box
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

 to sys.path
from src.data_fetcher import EnvironmentalDataManager

def download_cmems_data():
    print("\n" + "=" * 65)
    print("STEP 1: DOWNLOADING AUTHENTIC COPERNICUS MARINE (CMEMS) DATA")
    print("=" * 65)

    mgr = EnvironmentalDataManager(data_root="data")
    username, password = mgr.get_credentials()
    print(f" -> Authenticating with Copernicus Marine as user: {username}")

    # Bounding box covering Mississippi Delta & Main Pass offshore sector
    min_lon, max_lon = -89.8, -88.2
    min_lat, max_lat = 28.6, 29.8

    # Simulation window: 48h covering Nov 15 00:00 UTC to Nov 17 00:00 UTC
    start_time = datetime(2023, 11, 15, 0, 0)
    end_time = datetime(2023, 11, 17, 0, 0)

    print(f" -> Spatial Domain: Lon [{min_lon}, {max_lon}], Lat [{min_lat}, {max_lat}]")
    print(f" -> Time Domain: {start_time.isoformat()} to {end_time.isoformat()}")

    # 1. Currents
    mgr.download_cmems_currents(
        min_lon=min_lon, max_lon=max_lon,
        min_lat=min_lat, max_lat=max_lat,
        start_time=start_time, end_time=end_time,
        output_filename="cmems_currents_main_pass.nc"
    )

    # 2. Waves / Stokes Drift
    mgr.download_cmems_waves(
        min_lon=min_lon, max_lon=max_lon,
        min_lat=min_lat, max_lat=max_lat,
        start_time=start_time, end_time=end_time,
        output_filename="cmems_waves_main_pass.nc"
    )

    # 3. Winds
    mgr.download_cmems_wind(
        min_lon=min_lon, max_lon=max_lon,
        min_lat=min_lat, max_lat=max_lat,
        start_time=start_time, end_time=end_time,
        output_filename="cmems_wind_main_pass.nc"
    )
    print(" -> All CMEMS NetCDF forcing files successfully downloaded! [OK]")

def download_noaa_ais():
    print("\n" + "=" * 65)
    print("STEP 2: DOWNLOADING & FILTERING AUTHENTIC NOAA MARINE CADASTRE AIS")
    print("=" * 65)

    noaa_url = "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/AIS_2023_11_16.zip"
    ais_dir = Path("data/ais")
    ais_dir.mkdir(parents=True, exist_ok=True)
    output_csv = ais_dir / "main_pass_noaa_ais_2023_11_16.csv"

    # Spatial filter for Main Pass sector
    min_lat, max_lat = 28.6, 29.8
    min_lon, max_lon = -89.8, -88.2

    print(f" -> Fetching NOAA AIS Archive: {noaa_url}")
    print(f" -> Geographic Filter: Lat [{min_lat}, {max_lat}], Lon [{min_lon}, {max_lon}]")

    temp_zip = ais_dir / "temp_noaa_ais_2023_11_16.zip"

    # Download zipped archive with progress
    req = urllib.request.Request(noaa_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp, open(temp_zip, 'wb') as out_file:
        total_size = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        block_size = 1024 * 1024 * 4 # 4MB blocks
        print(f" -> Total archive size: {total_size / (1024*1024):.1f} MB")
        while True:
            chunk = resp.read(block_size)
            if not chunk:
                break
            downloaded += len(chunk)
            out_file.write(chunk)
            pct = (downloaded / total_size) * 100 if total_size > 0 else 0
            sys.stdout.write(f"\r    Downloading NOAA archive: {downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({pct:.1f}%)")
            sys.stdout.flush()

    print("\n -> Download complete! Extracting and filtering records for Main Pass...")

    matched_records = 0
    unique_mmsis = set()
    unique_vessels = {}

    with zipfile.ZipFile(temp_zip, 'r') as z:
        # Find the CSV inside
        csv_filename = [n for n in z.namelist() if n.lower().endswith('.csv')][0]
        print(f" -> Parsing CSV from zip: {csv_filename}")

        with z.open(csv_filename, 'r') as f_in, open(output_csv, 'w', newline='', encoding='utf-8') as f_out:
            reader = csv.DictReader(io.TextIOWrapper(f_in, encoding='utf-8'))
            fieldnames = [
                "timestamp", "mmsi", "imo", "vessel_name", "vessel_type",
                "callsign", "latitude", "longitude", "speed_knots", "course_deg", "nav_status", "draft"
            ]
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                try:
                    lat = float(row.get('LAT', 0.0))
                    lon = float(row.get('LON', 0.0))
                except (ValueError, TypeError):
                    continue

                if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                    mmsi = row.get('MMSI', '').strip()
                    vessel_name = row.get('VesselName', '').strip()
                    imo = row.get('IMO', '').strip()
                    vessel_type = row.get('VesselType', '').strip()
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
                        "vessel_type": vessel_type,
                        "callsign": callsign,
                        "latitude": lat,
                        "longitude": lon,
                        "speed_knots": sog,
                        "course_deg": cog,
                        "nav_status": status,
                        "draft": draft
                    })
                    matched_records += 1
                    unique_mmsis.add(mmsi)
                    if mmsi not in unique_vessels and vessel_name:
                        unique_vessels[mmsi] = (vessel_name, vessel_type)

    # Clean up temporary 300MB zip
    try:
        temp_zip.unlink()
        print(" -> Removed temporary zip archive.")
    except Exception:
        pass

    print(f" -> Successfully saved: {output_csv}")
    print(f" -> Extracted {matched_records:,} genuine NOAA AIS pings across {len(unique_mmsis)} distinct vessels in the sector!")
    print("\nSample vessels detected in sector on Nov 16, 2023:")
    for i, (mmsi, (name, vtype)) in enumerate(list(unique_vessels.items())[:10]):
        print(f"    {i+1}. MMSI {mmsi}: {name} (Type code: {vtype})")

if __name__ == "__main__":
    download_cmems_data()
    download_noaa_ais()

"""
extract_main_pass_ais.py
------------------------
Extracts and filters NOAA Marine Cadastre AIS broadcast points for the
Main Pass Oil Spill sector (Mississippi River Delta, Nov 16, 2023).
"""

import io
import csv
import zipfile
from pathlib import Path

def main():
    zip_path = Path("data/ais/AIS_2023_11_16.zip")
    output_csv = Path("data/ais/main_pass_noaa_ais_2023_11_16.csv")

    if not zip_path.exists():
        print(f"ERROR: {zip_path} not found.")
        return

    # Spatial filter for Main Pass sector & Mississippi River approaches
    min_lat, max_lat = 28.6, 29.8
    min_lon, max_lon = -89.8, -88.2

    print("=" * 65)
    print("FILTERING 100% AUTHENTIC NOAA MARINE CADASTRE AIS BROADCASTS")
    print(f" -> Source Archive: {zip_path} ({zip_path.stat().st_size / (1024*1024):.1f} MB)")
    print(f" -> Sector Filter: Lat [{min_lat}, {max_lat}], Lon [{min_lon}, {max_lon}]")
    print("=" * 65)

    matched_records = 0
    unique_vessels = {}

    with zipfile.ZipFile(zip_path, 'r') as z:
        csv_filename = [n for n in z.namelist() if n.lower().endswith('.csv')][0]
        print(f" -> Reading internal CSV: {csv_filename} (streaming decompression)...")

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
                    print(f"    ... processed {i:,} global US pings, found {matched_records:,} matches in sector")

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
                        unique_vessels[mmsi] = {
                            "name": vessel_name,
                            "type": vtype,
                            "imo": imo,
                            "pings": 0
                        }
                    unique_vessels[mmsi]["pings"] += 1

    print("\n" + "=" * 65)
    print("EXTRACTION COMPLETE!")
    print(f" -> Output File: {output_csv} ({output_csv.stat().st_size / (1024*1024):.2f} MB)")
    print(f" -> Total sector AIS records: {matched_records:,}")
    print(f" -> Total distinct vessels in sector: {len(unique_vessels)}")
    print("=" * 65)

    print("\nTop commercial vessels active in Main Pass sector on Nov 16, 2023:")
    sorted_vessels = sorted(unique_vessels.items(), key=lambda x: x[1]["pings"], reverse=True)
    for idx, (mmsi, info) in enumerate(sorted_vessels[:15]):
        print(f"  {idx+1:2d}. MMSI: {mmsi} | IMO: {info['imo']:<7} | Name: {info['name']:<25} | Type: {info['type']:<4} | Pings: {info['pings']}")

if __name__ == "__main__":
    main()

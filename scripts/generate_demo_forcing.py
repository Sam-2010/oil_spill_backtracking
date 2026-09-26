"""
generate_demo_forcing.py
------------------------
Generates CF-compliant NetCDF datasets for demo simulation:
- data/currents/demo_currents.nc (uo, vo)
- data/wind/demo_wind.nc (x_wind, y_wind)
- data/waves/demo_waves.nc (Stokes drift VSDX, VSDY, wave height)

Spatial domain covers the Gulf of Mexico (Green Canyon / Mississippi Delta sector):
Lon: [-90.8, -89.7], Lat: [27.2, 28.3]
Time domain: 2026-09-25 00:00 to 2026-09-26 12:00 UTC (37 hourly steps)
"""

import os
import sys
from pathlib import Path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from datetime import datetime
import numpy as np
import netCDF4 as nc

def main():
    print("=" * 65)
    print("GENERATING DEMO CF-COMPLIANT FORCING DATASETS")
    print("=" * 65)

    currents_dir = Path("data/currents")
    wind_dir = Path("data/wind")
    waves_dir = Path("data/waves")

    currents_dir.mkdir(parents=True, exist_ok=True)
    wind_dir.mkdir(parents=True, exist_ok=True)
    waves_dir.mkdir(parents=True, exist_ok=True)

    # Grid specifications
    min_lon, max_lon = -90.8, -89.7
    min_lat, max_lat = 27.2, 28.3
    res = 0.05

    lons = np.arange(min_lon, max_lon + res, res, dtype=np.float32)
    lats = np.arange(min_lat, max_lat + res, res, dtype=np.float32)

    # Time span: 37 hours covering the 24h backtrack window
    start_time = datetime(2026, 9, 25, 0, 0, 0)
    end_time = datetime(2026, 9, 26, 12, 0, 0)
    total_hours = int((end_time - start_time).total_seconds() / 3600) + 1
    times_seconds = np.arange(0, total_hours * 3600, 3600, dtype=np.int64)

    time_units = f"seconds since {start_time.strftime('%Y-%m-%d %H:%M:%S')}"

    print(f" -> Grid: {len(lats)} lat x {len(lons)} lon points ({min_lat:.2f} to {max_lat:.2f}N, {min_lon:.2f} to {max_lon:.2f}E)")
    print(f" -> Time steps: {total_hours} hourly frames ({start_time} to {end_time} UTC)")

    # -----------------------------------------------------------------
    # 1. Currents (uo, vo)
    # Gulf of Mexico shelf flow: westward/southwestward coastal current
    # uo ~ -0.20 m/s, vo ~ -0.10 m/s with diurnal tidal fluctuation
    # -----------------------------------------------------------------
    curr_file = currents_dir / "demo_currents.nc"
    with nc.Dataset(curr_file, "w", format="NETCDF4") as ds:
        ds.createDimension("time", total_hours)
        ds.createDimension("lat", len(lats))
        ds.createDimension("lon", len(lons))

        t_var = ds.createVariable("time", "i8", ("time",))
        t_var[:] = times_seconds
        t_var.units = time_units
        t_var.standard_name = "time"
        t_var.calendar = "gregorian"

        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lat_var[:] = lats
        lat_var.units = "degrees_north"
        lat_var.standard_name = "latitude"

        lon_var = ds.createVariable("lon", "f4", ("lon",))
        lon_var[:] = lons
        lon_var.units = "degrees_east"
        lon_var.standard_name = "longitude"

        uo_var = ds.createVariable("x_sea_water_velocity", "f4", ("time", "lat", "lon"), zlib=True)
        vo_var = ds.createVariable("y_sea_water_velocity", "f4", ("time", "lat", "lon"), zlib=True)
        uo_var.units = "m/s"
        uo_var.standard_name = "x_sea_water_velocity"
        vo_var.units = "m/s"
        vo_var.standard_name = "y_sea_water_velocity"

        for t_idx, t_sec in enumerate(times_seconds):
            t_hours = t_sec / 3600.0
            tide_phase = 2 * np.pi * t_hours / 24.84  # Diurnal tidal cycle
            # West-southwest drift typical of northern Gulf shelf
            u_val = -0.18 + 0.06 * np.cos(tide_phase)
            v_val = -0.09 + 0.05 * np.sin(tide_phase)
            uo_var[t_idx, :, :] = np.full((len(lats), len(lons)), u_val, dtype=np.float32)
            vo_var[t_idx, :, :] = np.full((len(lats), len(lons)), v_val, dtype=np.float32)

    print(f" -> Saved: {curr_file}")

    # -----------------------------------------------------------------
    # 2. Wind (x_wind, y_wind)
    # Gulf moderate southeasterly breeze ~ 5.0 - 7.0 m/s
    # -----------------------------------------------------------------
    wind_file = wind_dir / "demo_wind.nc"
    with nc.Dataset(wind_file, "w", format="NETCDF4") as ds:
        ds.createDimension("time", total_hours)
        ds.createDimension("lat", len(lats))
        ds.createDimension("lon", len(lons))

        t_var = ds.createVariable("time", "i8", ("time",))
        t_var[:] = times_seconds
        t_var.units = time_units
        t_var.standard_name = "time"
        t_var.calendar = "gregorian"

        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lat_var[:] = lats
        lat_var.units = "degrees_north"
        lat_var.standard_name = "latitude"

        lon_var = ds.createVariable("lon", "f4", ("lon",))
        lon_var[:] = lons
        lon_var.units = "degrees_east"
        lon_var.standard_name = "longitude"

        uw_var = ds.createVariable("x_wind", "f4", ("time", "lat", "lon"), zlib=True)
        vw_var = ds.createVariable("y_wind", "f4", ("time", "lat", "lon"), zlib=True)
        uw_var.units = "m/s"
        uw_var.standard_name = "x_wind"
        vw_var.units = "m/s"
        vw_var.standard_name = "y_wind"

        for t_idx, t_sec in enumerate(times_seconds):
            t_hours = t_sec / 3600.0
            # Easterly wind with diurnal breeze oscillation
            uw_val = -3.5 + 1.0 * np.sin(2 * np.pi * t_hours / 24.0)
            vw_val = 2.5 + 0.8 * np.cos(2 * np.pi * t_hours / 24.0)
            uw_var[t_idx, :, :] = np.full((len(lats), len(lons)), uw_val, dtype=np.float32)
            vw_var[t_idx, :, :] = np.full((len(lats), len(lons)), vw_val, dtype=np.float32)

    print(f" -> Saved: {wind_file}")

    # -----------------------------------------------------------------
    # 3. Wave Stokes Drift (VSDX, VSDY) & Significant Wave Height
    # Typical Gulf swell Stokes drift ~ 0.08 m/s aligned with wind
    # -----------------------------------------------------------------
    waves_file = waves_dir / "demo_waves.nc"
    with nc.Dataset(waves_file, "w", format="NETCDF4") as ds:
        ds.createDimension("time", total_hours)
        ds.createDimension("lat", len(lats))
        ds.createDimension("lon", len(lons))

        t_var = ds.createVariable("time", "i8", ("time",))
        t_var[:] = times_seconds
        t_var.units = time_units
        t_var.standard_name = "time"
        t_var.calendar = "gregorian"

        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lat_var[:] = lats
        lat_var.units = "degrees_north"
        lat_var.standard_name = "latitude"

        lon_var = ds.createVariable("lon", "f4", ("lon",))
        lon_var[:] = lons
        lon_var.units = "degrees_east"
        lon_var.standard_name = "longitude"

        sdx = ds.createVariable("sea_surface_wave_stokes_drift_x_velocity", "f4", ("time", "lat", "lon"), zlib=True)
        sdy = ds.createVariable("sea_surface_wave_stokes_drift_y_velocity", "f4", ("time", "lat", "lon"), zlib=True)
        vhm0 = ds.createVariable("sea_surface_wave_significant_height", "f4", ("time", "lat", "lon"), zlib=True)

        sdx.units = "m/s"
        sdx.standard_name = "sea_surface_wave_stokes_drift_x_velocity"
        sdy.units = "m/s"
        sdy.standard_name = "sea_surface_wave_stokes_drift_y_velocity"
        vhm0.units = "m"
        vhm0.standard_name = "sea_surface_wave_significant_height"

        for t_idx, t_sec in enumerate(times_seconds):
            sdx[t_idx, :, :] = np.full((len(lats), len(lons)), -0.05, dtype=np.float32)
            sdy[t_idx, :, :] = np.full((len(lats), len(lons)), 0.04, dtype=np.float32)
            vhm0[t_idx, :, :] = np.full((len(lats), len(lons)), 1.4, dtype=np.float32)

    print(f" -> Saved: {waves_file}")
    print("\nAll demo forcing datasets successfully generated! [OK]")

if __name__ == "__main__":
    main()

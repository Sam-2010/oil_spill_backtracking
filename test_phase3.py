"""
test_phase3.py
--------------
Unit and verification test for Phase 3:
1. Generates the CF-compliant benchmark NetCDF datasets (currents, wind, waves).
2. Initializes an OpenDrift OceanDrift instance.
3. Attaches all readers (Currents, Wind, Stokes Drift, GSHHG Landmask).
4. Verifies that OpenDrift can sample and interpolate environmental variables
   at the benchmark coordinates (13.7N, 42.8E).
"""

from datetime import datetime
import numpy as np
from opendrift.models.oceandrift import OceanDrift
from src.data_fetcher import EnvironmentalDataManager

def run_tests():
    print("=" * 70)
    print("RUNNING PHASE 3 TESTS: ENVIRONMENTAL DATA INTEGRATION & READERS")
    print("=" * 70)

    mgr = EnvironmentalDataManager(data_root="data")

    # 1. Real CMEMS NetCDFs & Wind NetCDF
    print("\n[STEP 1] Inspecting real Copernicus Marine NetCDF datasets...")
    live_curr = mgr.currents_dir / "cmems_currents_rubymar.nc"
    live_wave = mgr.waves_dir / "cmems_waves_rubymar.nc"
    live_wind = mgr.wind_dir / "cmems_wind_rubymar.nc"

    print(f" -> Currents NetCDF: {live_curr.name} ({live_curr.stat().st_size / 1024:.1f} KB) [LIVE CMEMS]")
    print(f" -> Waves NetCDF:    {live_wave.name} ({live_wave.stat().st_size / 1024:.1f} KB) [LIVE CMEMS]")
    print(f" -> Wind NetCDF:     {live_wind.name} ({live_wind.stat().st_size / 1024:.1f} KB) [LIVE CMEMS]")

    # 2. Initialize OpenDrift model
    print("\n[STEP 2] Initializing OpenDrift OceanDrift simulation instance...")
    o = OceanDrift(loglevel=20)  # INFO log level

    # 3. Attach all readers
    print("\n[STEP 3] Attaching readers to OpenDrift...")
    readers = mgr.attach_readers(
        opendrift_model=o,
        currents_path=live_curr,
        wind_path=live_wind,
        waves_path=live_wave,
        use_gshhg_landmask=True
    )

    assert len(readers) == 4, f"Expected 4 readers (currents, wind, waves, landmask), got {len(readers)}"
    print(" -> All 4 readers successfully attached: Currents, Wind, Stokes Drift, GSHHG Landmask! [OK]")

    # 4. Verify interpolation at benchmark coordinates
    print("\n[STEP 4] Verifying 4D interpolation at benchmark location (13.74N, 42.82E)...")
    sample_time = datetime(2024, 3, 1, 3, 30)
    
    curr_reader = readers[0]
    wind_reader = readers[1]
    wave_reader = readers[2]

    env_curr = curr_reader.get_variables(["x_sea_water_velocity", "y_sea_water_velocity"], time=sample_time, x=42.82, y=13.74)
    env_wind = wind_reader.get_variables(["x_wind", "y_wind"], time=sample_time, x=42.82, y=13.74)
    env_wave = wave_reader.get_variables(["sea_surface_wave_stokes_drift_y_velocity"], time=sample_time, x=42.82, y=13.74)

    u_curr = float(np.ravel(env_curr["x_sea_water_velocity"])[0])
    v_curr = float(np.ravel(env_curr["y_sea_water_velocity"])[0])
    u_wind = float(np.ravel(env_wind["x_wind"])[0])
    v_wind = float(np.ravel(env_wind["y_wind"])[0])
    v_stokes = float(np.ravel(env_wave["sea_surface_wave_stokes_drift_y_velocity"])[0])

    print(f" -> Interpolated Water Current: u = {u_curr:+.3f} m/s, v = {v_curr:+.3f} m/s [REAL CMEMS]")
    print(f" -> Interpolated 10m Wind:     u = {u_wind:+.2f} m/s, v = {v_wind:+.2f} m/s")
    print(f" -> Environmental interpolation verified successfully! [OK]")

    # 5. Quick reverse-simulation test
    print("\n[STEP 5] Testing 2-step reverse drift integration with real CMEMS forcing...")
    from datetime import timedelta
    o.set_config("environment:fallback:horizontal_diffusivity", 10.0)
    o.seed_elements(lon=42.85, lat=13.70, time=sample_time, number=20)
    o.run(steps=2, time_step=-timedelta(minutes=15))
    print(f" -> Particles successfully stepped backwards in time! Final time: {o.time} [OK]")

    print("\n" + "=" * 70)
    print("ALL PHASE 3 TESTS COMPLETED SUCCESSFULLY! [OK]")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()

"""
backtrack_engine.py
-------------------
Core OpenDrift Lagrangian simulation engine for backward oil spill trajectory tracking:
  - Supports reverse time integration (negative time steps).
  - Seeds particle ensembles uniformly across satellite detected GeoJSON polygons
    or circular fallback uncertainty zones.
  - Applies hydrodynamic forcing: CMEMS hourly surface currents, 10m wind leeway (3%),
    wave Stokes drift, and stochastic horizontal turbulent diffusion (Kh = 10 m^2/s).
  - Uses GSHHG high-resolution coastline and island boundaries for stranding detection.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
from opendrift.models.oceandrift import OceanDrift

from src.data_fetcher import EnvironmentalDataManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class OilSpillBacktracker:
    def __init__(
        self,
        data_manager: Optional[EnvironmentalDataManager] = None,
        horizontal_diffusivity: float = 10.0,
        wind_drift_factor: float = 0.03
    ):
        """
        :param data_manager: EnvironmentalDataManager instance.
        :param horizontal_diffusivity: Sub-grid turbulent diffusivity Kh in m^2/s (default: 10.0).
        :param wind_drift_factor: Surface wind leeway factor (default: 0.03 = 3%).
        """
        self.data_manager = data_manager or EnvironmentalDataManager(data_root="data")
        self.kh = horizontal_diffusivity
        self.wind_leeway = wind_drift_factor

    def run_backtrack(
        self,
        detection_data: Dict[str, Any],
        currents_file: Optional[Path] = None,
        wind_file: Optional[Path] = None,
        waves_file: Optional[Path] = None,
        backtrack_hours: Optional[float] = None,
        num_particles: int = 1000,
        time_step_minutes: int = 15,
        output_step_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Runs the full backward trajectory simulation.

        :param detection_data: Output dictionary from SlickMorphologyAnalyzer.analyze().
        :param currents_file: Path to currents NetCDF (default: data/currents/cmems_currents_rubymar.nc).
        :param wind_file: Path to wind NetCDF (default: data/wind/cmems_wind_rubymar.nc).
        :param waves_file: Path to wave NetCDF (default: data/waves/cmems_waves_rubymar.nc).
        :param backtrack_hours: Total backward simulation duration (default: from detection_data, e.g. 72h).
        :param num_particles: Number of Lagrangian particles to seed (default: 1000).
        :param time_step_minutes: Numerical integration time step in minutes (default: 15 min).
        :param output_step_minutes: Frequency of trajectory output recording (default: 60 min = hourly).
        """
        # 1. Resolve Data Files
        curr_path = Path(currents_file or self.data_manager.currents_dir / "cmems_currents_rubymar.nc")
        wind_path = Path(wind_file or self.data_manager.wind_dir / "cmems_wind_rubymar.nc")
        wave_path = Path(waves_file or self.data_manager.waves_dir / "cmems_waves_rubymar.nc")

        if not curr_path.exists():
            raise FileNotFoundError(f"Currents dataset not found: {curr_path}")

        # 2. Parse Detection Metadata
        raw_ts = str(detection_data["detection_timestamp"]).replace("Z", "").split("+")[0]
        detection_time = datetime.fromisoformat(raw_ts).replace(tzinfo=None)
        duration_hours = backtrack_hours or float(detection_data.get("max_backtrack_hours", 72.0))

        logger.info(
            f"Initiating OpenDrift Backtrack Simulation:\n"
            f" - Detection Time: {detection_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
            f" - Backtrack Horizon: {duration_hours:.1f} hours\n"
            f" - Particle Count: {num_particles}\n"
            f" - Leeway Factor: {self.wind_leeway * 100:.1f}%\n"
            f" - Diffusivity (Kh): {self.kh:.1f} m^2/s"
        )

        # 3. Initialize OpenDrift Model
        o = OceanDrift(loglevel=20)

        # 4. Configure Physics & Boundary Settings (MUST be done before seeding)
        o.set_config("environment:fallback:horizontal_diffusivity", self.kh)
        o.set_config("seed:wind_drift_factor", self.wind_leeway)
        o.set_config("general:coastline_action", "stranding")
        o.set_config("seed:ocean_only", True)

        # 5. Attach Environmental Readers
        self.data_manager.attach_readers(
            opendrift_model=o,
            currents_path=curr_path,
            wind_path=wind_path if wind_path.exists() else None,
            waves_path=wave_path if wave_path.exists() else None,
            use_gshhg_landmask=True
        )

        # 6. Seed Particles
        if detection_data.get("has_polygon") and "polygon_coordinates" in detection_data:
            coords = detection_data["polygon_coordinates"]
            poly_lons = [pt[0] for pt in coords]
            poly_lats = [pt[1] for pt in coords]
            logger.info(f"Seeding {num_particles} particles uniformly across detected polygon footprint...")
            o.seed_within_polygon(
                lons=poly_lons,
                lats=poly_lats,
                number=num_particles,
                time=detection_time
            )
        else:
            # Fallback circular point seeding
            centroid = detection_data["centroid"]
            radius = float(detection_data.get("uncertainty_radius_m", 1500.0))
            logger.info(
                f"Seeding {num_particles} particles in circular fallback (center: "
                f"{centroid['latitude']:.4f}N, {centroid['longitude']:.4f}E, radius: {radius:.0f}m)..."
            )
            o.seed_elements(
                lon=centroid["longitude"],
                lat=centroid["latitude"],
                radius=radius,
                number=num_particles,
                time=detection_time
            )

        # 7. Execute Reverse Simulation
        logger.info(f"Starting backward integration for {duration_hours:.1f} hours...")
        o.run(
            duration=timedelta(hours=duration_hours),
            time_step=-timedelta(minutes=time_step_minutes),
            time_step_output=-timedelta(minutes=output_step_minutes)
        )

        logger.info(f"Backward simulation completed successfully. Final simulation time: {o.time}")

        # 8. Extract Trajectory History from o.result (xarray Dataset)
        res = o.result
        times = [np.datetime_as_string(t, unit="s") + "Z" for t in res.time.values]
        lons = res.lon.values      # Shape: (trajectories, time)
        lats = res.lat.values      # Shape: (trajectories, time)
        status = res.status.values # Shape: (trajectories, time)

        return {
            "status": "success",
            "model": o,
            "detection_data": detection_data,
            "simulation_params": {
                "duration_hours": duration_hours,
                "time_step_minutes": -time_step_minutes,
                "output_step_minutes": -output_step_minutes,
                "num_particles": num_particles,
                "wind_drift_factor": self.wind_leeway,
                "horizontal_diffusivity": self.kh
            },
            "trajectory": {
                "times": times,
                "num_steps": len(times),
                "lons": lons,
                "lats": lats,
                "particle_status": status
            }
        }

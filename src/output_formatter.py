"""
output_formatter.py
-------------------
Processes OpenDrift trajectory simulations and formats the output into:
  1. Standardized GeoJSON FeatureCollection (outputs/trajectory_corridor.geojson)
     specifically tailored as a spatial-temporal query envelope for downstream AIS modules.
  2. Summary Origin Report JSON (outputs/origin_report.json).
  3. Visual trajectory plot (outputs/trajectory_plot.png) rendering the reverse
     particle trajectories, initial slick, and primary origin candidate zone.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import MultiPoint, Polygon, Point, mapping, shape
from shapely.ops import unary_union

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class TrajectoryOutputFormatter:
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def format_and_export(
        self,
        simulation_result: Dict[str, Any],
        geojson_filename: str = "trajectory_corridor.geojson",
        report_filename: str = "origin_report.json",
        map_filename: str = "trajectory_map.html"
    ) -> Dict[str, Path]:
        """
        Main formatter and exporter.
        """
        traj = simulation_result["trajectory"]
        detection = simulation_result["detection_data"]
        times = traj["times"]
        lons = traj["lons"]
        lats = traj["lats"]
        num_steps = traj["num_steps"]

        logger.info(f"Formatting trajectory history across {num_steps} hourly steps...")

        # 1. Process Hourly Steps & Compute Spatial Envelopes
        hourly_corridor = []
        hourly_polygons = []

        for step_idx in range(num_steps):
            step_time = times[step_idx]
            step_lons = lons[:, step_idx]
            step_lats = lats[:, step_idx]

            # Filter valid (active, non-stranded) particles
            valid_mask = ~np.isnan(step_lons) & ~np.isnan(step_lats)
            valid_lons = step_lons[valid_mask]
            valid_lats = step_lats[valid_mask]

            if len(valid_lons) < 3:
                continue

            centroid_lat, centroid_lon = self._find_density_peak(valid_lons, valid_lats)

            # 95% Confidence Spatial Hull
            # Exclude extreme 5% outliers from centroid
            dists = np.hypot(valid_lons - centroid_lon, valid_lats - centroid_lat)
            pct95_mask = dists <= np.percentile(dists, 95)
            pts_95 = [
                (float(valid_lons[i]), float(valid_lats[i]))
                for i in range(len(valid_lons)) if pct95_mask[i]
            ]

            poly = MultiPoint(pts_95).convex_hull
            if isinstance(poly, Polygon):
                # Apply slight buffer to represent physical particle dispersion width
                poly_buffered = poly.buffer(0.005)  # ~500m buffer
            else:
                poly_buffered = Point(centroid_lon, centroid_lat).buffer(0.01)

            step_record = {
                "step_index": step_idx,
                "timestamp": step_time,
                "hours_prior": step_idx,
                "centroid": [centroid_lat, centroid_lon],
                "active_particles": int(len(valid_lons)),
                "polygon": poly_buffered
            }
            hourly_corridor.append(step_record)
            hourly_polygons.append(poly_buffered)

        # 2. Origin Solver: Coastal Stranding Convergence or Morphology Window Correlation
        origin_window = detection.get("estimated_origin_window_utc", {})
        start_time_iso = origin_window.get("start")
        end_time_iso = origin_window.get("end")

        candidate_polygons = []
        candidate_centroids = []

        if start_time_iso and end_time_iso:
            start_dt = datetime.fromisoformat(start_time_iso)
            end_dt = datetime.fromisoformat(end_time_iso)

            for step in hourly_corridor:
                t = datetime.fromisoformat(step["timestamp"].replace("Z", "+00:00"))
                if start_dt <= t <= end_dt:
                    candidate_polygons.append(step["polygon"])
                    candidate_centroids.append(step["centroid"])

        # Check for coastal stranding convergence across the full trajectory
        num_particles = lons.shape[0]
        stranded_pts = []
        for i in range(num_particles):
            valid_idx = np.where(~np.isnan(lons[i, :]))[0]
            if len(valid_idx) > 0:
                last_idx = valid_idx[-1]
                if last_idx < num_steps - 1:
                    stranded_pts.append((float(lons[i, last_idx]), float(lats[i, last_idx])))

        stranded_fraction = len(stranded_pts) / float(num_particles) if num_particles > 0 else 0.0

        if stranded_fraction >= 0.15:
            # High-confidence coastal / reef convergence detected
            logger.info(
                f"Coastal stranding convergence detected: {len(stranded_pts)} of {num_particles} "
                f"({stranded_fraction*100:.1f}%) particles converged on shoreline/reef."
            )
            strand_lons = np.array([p[0] for p in stranded_pts])
            strand_lats = np.array([p[1] for p in stranded_pts])
            peak_lat, peak_lon = self._find_density_peak(strand_lons, strand_lats)
            primary_centroid = [peak_lat, peak_lon]

            # 95% Confidence Spatial Hull around stranded cluster
            dists = np.hypot(strand_lons - peak_lon, strand_lats - peak_lat)
            pct95_mask = dists <= np.percentile(dists, 95)
            pts_95 = [
                (float(strand_lons[k]), float(strand_lats[k]))
                for k in range(len(strand_lons)) if pct95_mask[k]
            ]
            strand_poly = MultiPoint(pts_95).convex_hull
            if isinstance(strand_poly, Polygon):
                primary_origin_poly = strand_poly.buffer(0.005)
            else:
                primary_origin_poly = Point(peak_lon, peak_lat).buffer(0.01)

            solver_method = "coastal_stranding_convergence"
            confidence = f"high ({stranded_fraction*100:.0f}% coastal convergence)"
        elif candidate_polygons:
            primary_origin_poly = unary_union(candidate_polygons).convex_hull
            if not isinstance(primary_origin_poly, Polygon):
                primary_origin_poly = primary_origin_poly.buffer(0.01)
            c_lons = np.array([c[1] for c in candidate_centroids])
            c_lats = np.array([c[0] for c in candidate_centroids])
            peak_lat, peak_lon = self._find_density_peak(c_lons, c_lats)
            primary_centroid = [peak_lat, peak_lon]
            solver_method = "morphology_diffusion_correlated"
            confidence = "high"
        else:
            # Fallback: take final 3 hours of simulation
            tail_polys = hourly_polygons[-3:] if len(hourly_polygons) >= 3 else hourly_polygons
            primary_origin_poly = unary_union(tail_polys).convex_hull
            if not isinstance(primary_origin_poly, Polygon):
                primary_origin_poly = primary_origin_poly.buffer(0.01)
            primary_centroid = hourly_corridor[-1]["centroid"]
            solver_method = "full_horizon_terminal"
            confidence = "low (fallback)"

        morph_data = detection.get("morphology") or {}
        calc_hours = morph_data.get("calculated_elapsed_hours")
        reported_hours = round(float(calc_hours), 1) if calc_hours is not None else float(len(hourly_corridor) - 1)

        # 3. Build Standardized GeoJSON FeatureCollection
        features = []

        # Feature A: Initial Detection Footprint
        if detection.get("has_polygon") and "polygon_coordinates" in detection:
            det_poly_coords = detection["polygon_coordinates"]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [det_poly_coords]
                },
                "properties": {
                    "layer": "detection_footprint",
                    "timestamp": detection["detection_timestamp"],
                    "hours_prior": 0.0,
                    "incident_name": detection.get("incident_name", "Oil Spill Detection")
                }
            })

        # Feature B: Primary Origin Candidate Polygon (for AIS queries)
        features.append({
            "type": "Feature",
            "geometry": mapping(primary_origin_poly),
            "properties": {
                "layer": "primary_origin_candidate",
                "timestamp": f"{start_time_iso} to {end_time_iso}" if start_time_iso else f"{times[-1]} to {times[0]}",
                "hours_prior": reported_hours,
                "centroid_latitude": primary_centroid[0],
                "centroid_longitude": primary_centroid[1],
                "solver_method": solver_method,
                "confidence_level": confidence,
                "description": "High-confidence origin search area for AIS vessel matching"
            }
        })

        # Features C: Hourly Backtrack Corridor Polygons
        for step in hourly_corridor:
            features.append({
                "type": "Feature",
                "geometry": mapping(step["polygon"]),
                "properties": {
                    "layer": "hourly_backtrack_corridor",
                    "step_index": step["step_index"],
                    "timestamp": step["timestamp"],
                    "hours_prior": step["hours_prior"],
                    "active_particles": step["active_particles"],
                    "centroid_latitude": step["centroid"][0],
                    "centroid_longitude": step["centroid"][1]
                }
            })

        geojson_payload = {
            "type": "FeatureCollection",
            "metadata": {
                "module": "Oil Spill Backtracking & Origin Identification",
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "total_backtrack_hours": len(hourly_corridor) - 1,
                "warning": detection.get("warning")
            },
            "features": features
        }

        # 4. Save GeoJSON File
        geojson_path = self.output_dir / geojson_filename
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson_payload, f, indent=2)
        logger.info(f"Exported GeoJSON trajectory corridor to {geojson_path}")

        # 5. Save Summary Report JSON
        report_payload = {
            "status": "success",
            "warning": detection.get("warning"),
            "detection_metadata": {
                "timestamp": detection["detection_timestamp"],
                "centroid": detection["centroid"],
                "has_polygon": detection.get("has_polygon", False)
            },
            "morphology_analysis": detection.get("morphology"),
            "estimated_origin": {
                "time_window_utc": origin_window,
                "primary_centroid": {
                    "latitude": primary_centroid[0],
                    "longitude": primary_centroid[1]
                },
                "solver_method": solver_method,
                "confidence": confidence
            },
            "simulation_summary": {
                "total_steps": len(hourly_corridor),
                "total_hours_backtracked": len(hourly_corridor) - 1,
                "start_time": times[0],
                "end_time": times[-1]
            }
        }

        report_path = self.output_dir / report_filename
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)
        logger.info(f"Exported summary report to {report_path}")

        # 6. Generate Interactive Web Map (Folium)
        map_path = self.output_dir / map_filename
        try:
            self._generate_interactive_map(
                geojson_payload=geojson_payload,
                primary_centroid=primary_centroid,
                output_file=map_path
            )
        except Exception as e:
            logger.warning(f"Interactive map rendering skipped due to: {e}")
            map_path = None

        return {
            "geojson": geojson_path,
            "report": report_path,
            "map": map_path
        }

    def _generate_interactive_map(
        self,
        geojson_payload: Dict[str, Any],
        primary_centroid: List[float],
        output_file: Path
    ):
        """
        Renders an interactive HTML map using Folium with satellite-like OpenStreetMap tiles,
        polygons for detected slicks, and origin candidate zones.
        """
        import folium

        # Initialize map with satellite and ocean/street base layers (avoids OSM 403 file:// tile block)
        m = folium.Map(
            location=[primary_centroid[0], primary_centroid[1]],
            zoom_start=9,
            tiles=None
        )

        # Base Layer 1: Esri World Imagery (High-res Satellite)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Satellite (Esri)",
            control=True
        ).add_to(m)

        # Base Layer 2: CartoDB Voyager (Clear marine/coastal map)
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
            attr="&copy; OpenStreetMap contributors &copy; CARTO",
            name="CartoDB Navigation Map",
            control=True
        ).add_to(m)

        # Style function for different layers
        def style_fn(feature):
            layer = feature["properties"].get("layer", "")
            if layer == "detection_footprint":
                return {
                    "fillColor": "#e63946",
                    "color": "#d90429",
                    "weight": 2.5,
                    "fillOpacity": 0.4
                }
            elif layer == "primary_origin_candidate":
                return {
                    "fillColor": "#2a9d8f",
                    "color": "#1b4332",
                    "weight": 3.0,
                    "dashArray": "5, 5",
                    "fillOpacity": 0.5
                }
            else:  # hourly_backtrack_corridor
                return {
                    "fillColor": "#457b9d",
                    "color": "#1d3557",
                    "weight": 1.0,
                    "fillOpacity": 0.15
                }

        # Add GeoJSON layer
        folium.GeoJson(
            geojson_payload,
            name="Oil Spill Backtrack Corridor",
            style_function=style_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=["layer", "timestamp", "hours_prior"],
                aliases=["Layer:", "Time:", "Hours Prior:"],
                localize=True
            ),
            popup=folium.GeoJsonPopup(
                fields=["layer", "timestamp", "hours_prior"],
                aliases=["Layer:", "Time:", "Hours Prior:"]
            )
        ).add_to(m)

        # Add Origin Centroid marker
        folium.Marker(
            location=[primary_centroid[0], primary_centroid[1]],
            popup=f"<b>Primary Origin Centroid</b><br>Lat: {primary_centroid[0]:.4f}N<br>Lon: {primary_centroid[1]:.4f}E",
            tooltip="Estimated Origin Centroid",
            icon=folium.Icon(color="green", icon="crosshairs", prefix="fa")
        ).add_to(m)

        # Layer Control
        folium.LayerControl().add_to(m)

        m.save(str(output_file))
        logger.info(f"Saved interactive HTML trajectory map to {output_file}")

    def _find_density_peak(self, lons: np.ndarray, lats: np.ndarray) -> Tuple[float, float]:
        """
        Pure NumPy 2D spatial density peak solver.
        Bins coordinates into a spatial grid and finds the center of the highest-density bin.
        Avoids C-level LAPACK/OpenBLAS crashes on Windows background processes.
        """
        if len(lons) < 3:
            return float(np.mean(lats)), float(np.mean(lons))
        try:
            hist, xedges, yedges = np.histogram2d(lons, lats, bins=25)
            max_idx = np.unravel_index(np.argmax(hist), hist.shape)
            peak_lon = float(0.5 * (xedges[max_idx[0]] + xedges[max_idx[0] + 1]))
            peak_lat = float(0.5 * (yedges[max_idx[1]] + yedges[max_idx[1] + 1]))
            return peak_lat, peak_lon
        except Exception:
            return float(np.mean(lats)), float(np.mean(lons))


"""
morphology.py
-------------
Analyzes oil slick geometry and morphology from detected satellite polygons.
Extracts:
  - Oriented bounding box (OBB)
  - Slick length and principal drift/travel axis
  - Head width (freshest oil) vs Tail width (weathered, diffused oil)
  - Estimated elapsed age (Delta T) using lateral turbulent diffusion:
        Delta T = (W_tail^2 - W_head^2) / (8 * Kh)
  - Fallback handler for circular point detections with explicit warning logs.
"""

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional

import numpy as np
import pyproj
from shapely.geometry import Polygon, Point, shape
from shapely.ops import transform

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SlickMorphologyAnalyzer:
    def __init__(self, horizontal_diffusivity_m2s: float = 10.0):
        """
        :param horizontal_diffusivity_m2s: Sub-grid turbulent diffusivity Kh in m^2/s.
                                          Standard oceanographic value: 5.0 to 15.0 m^2/s.
        """
        self.kh = horizontal_diffusivity_m2s

    def analyze(self, input_data: Any, head_only: bool = False) -> Dict[str, Any]:
        """
        Main entry point. Accepts:
          - Path to GeoJSON or JSON file (str)
          - Parsed dictionary (GeoJSON Feature / FeatureCollection / Fallback point dict)
          :param head_only: If True, automatically segments and seeds only the narrow head/core boil of elongated plumes.
        """
        data = self._load_data(input_data)
        geom, props = self._extract_geometry_and_props(data)

        detection_time_str = (
            props.get("detection_timestamp") 
            or props.get("detected_at") 
            or props.get("timestamp")
        )
        if not detection_time_str:
            raise ValueError(
                "Input data must specify 'detection_timestamp' (or 'detected_at' / 'timestamp') in ISO 8601 UTC format."
            )
        
        detection_time = datetime.fromisoformat(detection_time_str.replace("Z", "+00:00"))
        max_horizon_hours = float(props.get("max_backtrack_hours", 72))

        if geom is None or geom.geom_type not in ["Polygon", "MultiPolygon"]:
            return self._handle_fallback(data, props, detection_time, max_horizon_hours)

        return self._analyze_polygon(geom, props, detection_time, max_horizon_hours, head_only=head_only)

    def _load_data(self, input_data: Any) -> Dict[str, Any]:
        if isinstance(input_data, str):
            with open(input_data, "r", encoding="utf-8") as f:
                return json.load(f)
        elif isinstance(input_data, dict):
            return input_data
        else:
            raise TypeError(f"Unsupported input type: {type(input_data)}. Expected file path or dict.")

    def _extract_geometry_and_props(self, data: Dict[str, Any]) -> Tuple[Optional[Any], Dict[str, Any]]:
        # Case 1: GeoJSON Feature
        if data.get("type") == "Feature":
            geom = shape(data.get("geometry", {})) if data.get("geometry") else None
            return geom, data.get("properties", {})
        
        # Case 2: GeoJSON FeatureCollection
        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
            if not features:
                return None, {}
            # When multiple features exist, select the primary slick (largest area)
            valid_shapes = [
                (shape(f["geometry"]), f.get("properties", {}))
                for f in features
                if f.get("geometry")
            ]
            if not valid_shapes:
                return None, {}
            valid_shapes.sort(key=lambda item: item[0].area, reverse=True)
            primary_geom, primary_props = valid_shapes[0]
            return primary_geom, primary_props

        # Case 3: Direct Polygon geometry
        if data.get("type") in ["Polygon", "MultiPolygon"]:
            return shape(data), {}

        # Case 4: Fallback / flat point dictionary
        return None, data

    def _handle_fallback(
        self,
        raw_data: Dict[str, Any],
        props: Dict[str, Any],
        detection_time: datetime,
        max_horizon_hours: float
    ) -> Dict[str, Any]:
        """
        Handles point-only or non-polygon input. Emits explicit fallback warning.
        """
        lat = props.get("latitude") or raw_data.get("latitude")
        lon = props.get("longitude") or raw_data.get("longitude")
        radius_m = float(props.get("uncertainty_radius_m") or raw_data.get("uncertainty_radius_m", 1500.0))

        if lat is None or lon is None:
            raise ValueError("Input lacks polygon geometry and does not provide 'latitude' and 'longitude' for fallback.")

        warning_msg = (
            f"[WARNING] No polygon geometry detected. Using circular fallback (center: {lat:.4f}N, "
            f"{lon:.4f}E, radius: {radius_m:.0f}m). Morphology-based elapsed age estimation is unavailable; "
            f"full backtrack horizon ({max_horizon_hours:.0f}h) will be evaluated."
        )
        logger.warning(warning_msg)

        start_time = detection_time - timedelta(hours=max_horizon_hours)

        return {
            "has_polygon": False,
            "fallback_used": True,
            "warning": warning_msg,
            "detection_timestamp": detection_time.isoformat(),
            "centroid": {"latitude": float(lat), "longitude": float(lon)},
            "uncertainty_radius_m": radius_m,
            "max_backtrack_hours": max_horizon_hours,
            "morphology": None,
            "estimated_origin_window_utc": {
                "start": start_time.isoformat(),
                "end": detection_time.isoformat(),
                "confidence": "low (unconstrained fallback)"
            }
        }

    def _analyze_polygon(
        self,
        poly_wgs84: Polygon,
        props: Dict[str, Any],
        detection_time: datetime,
        max_horizon_hours: float,
        head_only: bool = False
    ) -> Dict[str, Any]:
        """
        Projects polygon to a local metric projection and analyzes morphology.
        """
        centroid_lon = poly_wgs84.centroid.x
        centroid_lat = poly_wgs84.centroid.y

        # Define local Azimuthal Equidistant projection centered on the slick centroid
        aeqd_proj = pyproj.CRS.from_proj4(
            f"+proj=aeqd +lat_0={centroid_lat} +lon_0={centroid_lon} +datum=WGS84 +units=m"
        )
        wgs84_proj = pyproj.CRS.from_epsg(4326)
        to_metric = pyproj.Transformer.from_crs(wgs84_proj, aeqd_proj, always_xy=True).transform
        to_wgs84 = pyproj.Transformer.from_crs(aeqd_proj, wgs84_proj, always_xy=True).transform

        poly_metric = transform(to_metric, poly_wgs84)

        # Minimum Area Rotated Bounding Box
        mrr = poly_metric.minimum_rotated_rectangle
        mrr_coords = list(mrr.exterior.coords)[:-1]

        # Calculate edge lengths to find length and width
        edges = []
        for i in range(4):
            p1 = np.array(mrr_coords[i])
            p2 = np.array(mrr_coords[(i + 1) % 4])
            length = np.linalg.norm(p2 - p1)
            edges.append((length, p1, p2))
        
        edges.sort(key=lambda x: x[0], reverse=True)
        length_m = edges[0][0]
        avg_width_m = edges[2][0]

        # Principal axis direction vector
        long_edge_p1 = edges[0][1]
        long_edge_p2 = edges[0][2]
        axis_vec = long_edge_p2 - long_edge_p1
        axis_unit = axis_vec / np.linalg.norm(axis_vec)
        orientation_deg = math.degrees(math.atan2(axis_unit[1], axis_unit[0])) % 360

        # Sample polygon vertices along the principal axis
        poly_coords = np.array(poly_metric.exterior.coords)
        projections = np.dot(poly_coords, axis_unit)
        min_proj, max_proj = np.min(projections), np.max(projections)
        total_span = max_proj - min_proj

        # Measure width near tip A (first 15%) and tip B (last 15%)
        tip_a_mask = projections <= (min_proj + 0.15 * total_span)
        tip_b_mask = projections >= (max_proj - 0.15 * total_span)

        perp_unit = np.array([-axis_unit[1], axis_unit[0]])
        tip_a_widths = np.dot(poly_coords[tip_a_mask], perp_unit)
        tip_b_widths = np.dot(poly_coords[tip_b_mask], perp_unit)

        width_a = (np.max(tip_a_widths) - np.min(tip_a_widths)) if len(tip_a_widths) > 0 else avg_width_m
        width_b = (np.max(tip_b_widths) - np.min(tip_b_widths)) if len(tip_b_widths) > 0 else avg_width_m

        # The narrower end is the head (fresh release); the wider end is the tail (weathered)
        if width_a < width_b:
            w_head, w_tail = width_a, width_b
            head_mask = tip_a_mask
        else:
            w_head, w_tail = width_b, width_a
            head_mask = tip_b_mask

        # If head-only segmentation is enabled for continuous plumes:
        if head_only and np.sum(head_mask) >= 3:
            from shapely.geometry import MultiPoint
            head_pts = [tuple(p) for p in poly_coords[head_mask]]
            head_poly_m = MultiPoint(head_pts).convex_hull.buffer(max(w_head * 0.1, 50.0))
            poly_wgs84 = transform(to_wgs84, head_poly_m)
            poly_metric = head_poly_m
            centroid_lon = poly_wgs84.centroid.x
            centroid_lat = poly_wgs84.centroid.y
            length_m = max(float(w_head * 1.5), 500.0)
            w_tail = w_head * 1.2
            logger.info("Auto-segmented narrow head/core boil from elongated plume for point-source tracking.")

        # Ensure minimal physical baseline width
        w_head = max(w_head, 50.0)
        w_tail = max(w_tail, w_head + 10.0)

        # Elapsed age estimation:
        if head_only:
            # For actively surfacing emergence boils, oil age at the boil head is < 1.0 hr
            elapsed_hours = 0.5
        else:
            # 1. Lateral turbulent diffusion: Delta T_diff = (W_tail^2 - W_head^2) / (8 * Kh)
            delta_t_seconds = (w_tail**2 - w_head**2) / (8.0 * self.kh)
            elapsed_hours_diff = delta_t_seconds / 3600.0

            # 2. Dual consistency check: Length-advection lower bound
            # In elongated slicks/plumes (continuous seeps or wind-streaked plumes), lateral spread is
            # suppressed by Langmuir circulation. An elongated plume of length L requires advective transit:
            # T_advect = L / v_drift (where typical surface drift v_drift ~ 0.35 m/s).
            v_drift_typical_ms = 0.35
            elapsed_hours_advect = (length_m / v_drift_typical_ms) / 3600.0

            # Harmonize diffusion and advection estimates:
            elapsed_hours = max(elapsed_hours_diff, elapsed_hours_advect * 0.75)

        # Bound by max_backtrack_hours ceiling
        elapsed_hours_clamped = min(elapsed_hours, max_horizon_hours)

        # Origin time window (with +- 25% uncertainty bracket)
        hours_min = max(0.5, elapsed_hours_clamped * 0.75)
        hours_max = min(max_horizon_hours, elapsed_hours_clamped * 1.25)

        origin_start = detection_time - timedelta(hours=hours_max)
        origin_end = detection_time - timedelta(hours=hours_min)

        logger.info(
            f"Morphology analysis successful: Length={length_m/1000.0:.2f}km, "
            f"W_head={w_head:.0f}m, W_tail={w_tail:.0f}m -> Elapsed Age={elapsed_hours_clamped:.1f}h "
            f"(Window: [{origin_start.strftime('%Y-%m-%d %H:%M')}, {origin_end.strftime('%Y-%m-%d %H:%M')} UTC])"
        )

        return {
            "has_polygon": True,
            "fallback_used": False,
            "warning": None,
            "detection_timestamp": detection_time.isoformat(),
            "polygon_coordinates": [list(pt) for pt in poly_wgs84.exterior.coords],
            "centroid": {"latitude": float(centroid_lat), "longitude": float(centroid_lon)},
            "area_km2": float(poly_metric.area / 1e6),
            "max_backtrack_hours": max_horizon_hours,
            "morphology": {
                "length_km": float(length_m / 1000.0),
                "head_width_m": float(w_head),
                "tail_width_m": float(w_tail),
                "orientation_deg": float(orientation_deg),
                "horizontal_diffusivity_m2s": self.kh,
                "calculated_elapsed_hours": float(elapsed_hours_clamped)
            },
            "estimated_origin_window_utc": {
                "start": origin_start.isoformat(),
                "end": origin_end.isoformat(),
                "hours_prior_min": float(hours_min),
                "hours_prior_max": float(hours_max),
                "confidence": "high (morphology-diffusion constrained)"
            }
        }

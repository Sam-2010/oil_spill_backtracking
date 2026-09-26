from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from shapely.geometry import Polygon, Point, LineString, MultiLineString
import geopandas as gpd

@dataclass
class TimeWindow:
    t0: datetime
    delta_t_hours: float
    start_time: datetime
    end_time: datetime
    buffered_start: datetime
    buffered_end: datetime

@dataclass
class PreflightResult:
    passed: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OriginMetadata:
    t0: datetime
    delta_t_hours: float
    primary_centroid: Point
    origin_polygon: Optional[Polygon]
    orientation_deg: float
    time_window: TimeWindow

@dataclass
class InterpolatedPoint:
    timestamp: datetime
    latitude: float
    longitude: float
    speed_knots: float
    course_deg: float
    is_interpolated: bool

@dataclass
class TrajectoryGap:
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    start_point: Point
    end_point: Point
    last_speed: float
    last_course: float

@dataclass
class VesselTrajectory:
    mmsi: int
    vessel_name: str
    vessel_type: Optional[int]
    callsign: Optional[str]
    raw_points_count: int
    interpolated_points: List[InterpolatedPoint]
    linestring: Optional[LineString]
    avg_speed: float
    min_speed: float
    max_speed: float
    speed_std: float
    loitering_detected: bool
    gaps: List[TrajectoryGap]

@dataclass
class DarkShipCandidate:
    mmsi: int
    vessel_name: str
    vessel_type: Optional[int]
    callsign: Optional[str]
    gap_start_time: datetime
    gap_end_time: datetime
    gap_duration_minutes: float
    drop_point: Point
    reemergence_point: Point
    last_speed_knots: float
    last_course_deg: float
    connecting_speed_knots: float
    is_kinematically_plausible: bool
    temporal_overlap: bool
    intersects_origin_zone: bool
    min_distance_to_centroid_meters: float
    projected_geometry: LineString

@dataclass
class VesselCPA:
    mmsi: int
    vessel_name: str
    vessel_type: Optional[int]
    callsign: Optional[str]
    is_dark_ship: bool
    cpa_timestamp: datetime
    cpa_point: Point
    cpa_distance_meters: float
    speed_at_cpa: float
    course_at_cpa: float
    intersects_origin_polygon: bool
    time_offset_from_release_hours: float
    is_within_release_window: bool
    slick_alignment_diff_deg: float

@dataclass
class ScoredCandidate:
    mmsi: int
    vessel_name: str
    vessel_type: Optional[int]
    callsign: Optional[str]
    is_dark_ship: bool
    cpa_distance_meters: float
    cpa_timestamp: datetime
    speed_at_cpa: float
    course_at_cpa: float
    s_prox: float
    s_time: float
    s_type: float
    s_align: float
    s_gap: float
    total_score: float
    suspicion_level: str
    weights_applied: Dict[str, float]
    audit_rationale: str
    cpa_point: Point

@dataclass
class ForensicVerdict:
    primary_verdict: str
    confidence: str
    summary: str
    top_vessel_candidate: Optional[Dict[str, Any]] = None
    nearest_infrastructure: Optional[Dict[str, Any]] = None
    anchor_strike_suspect: Optional[Dict[str, Any]] = None

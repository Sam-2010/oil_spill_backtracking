import os
from typing import Optional, Dict, Any, Tuple, List
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, box
from shapely.strtree import STRtree
from .models import TimeWindow, OriginMetadata

GOM_UTM_CRS = "EPSG:32616"

class InfrastructureIndex:
    """Fast spatial index for subsea pipelines and platforms with distance querying."""
    def __init__(self, pipelines_gdf: gpd.GeoDataFrame, platforms_gdf: gpd.GeoDataFrame, metric_crs: str = GOM_UTM_CRS):
        self.metric_crs = metric_crs
        
        self.pipes_wgs84 = pipelines_gdf
        self.plats_wgs84 = platforms_gdf
        
        self.pipes_utm = pipelines_gdf.to_crs(metric_crs) if not pipelines_gdf.empty else gpd.GeoDataFrame(crs=metric_crs)
        self.plats_utm = platforms_gdf.to_crs(metric_crs) if not platforms_gdf.empty else gpd.GeoDataFrame(crs=metric_crs)
        
        self.pipe_tree = STRtree(self.pipes_utm.geometry) if not self.pipes_utm.empty else None
        self.plat_tree = STRtree(self.plats_utm.geometry) if not self.plats_utm.empty else None

    def query_nearest_pipeline(self, pt_wgs84: Point) -> Tuple[Optional[Dict[str, Any]], float]:
        if self.pipes_utm.empty or self.pipe_tree is None:
            return None, float("inf")
            
        pt_gdf = gpd.GeoSeries([pt_wgs84], crs="EPSG:4326").to_crs(self.metric_crs)
        pt_utm = pt_gdf.iloc[0]
        
        nearest_idx = self.pipe_tree.nearest(pt_utm)
        nearest_geom = self.pipes_utm.geometry.iloc[nearest_idx]
        dist_m = float(pt_utm.distance(nearest_geom))
        
        row = self.pipes_wgs84.iloc[nearest_idx].to_dict()
        row["distance_meters"] = dist_m
        return row, dist_m

    def query_nearest_platform(self, pt_wgs84: Point) -> Tuple[Optional[Dict[str, Any]], float]:
        if self.plats_utm.empty or self.plat_tree is None:
            return None, float("inf")
            
        pt_gdf = gpd.GeoSeries([pt_wgs84], crs="EPSG:4326").to_crs(self.metric_crs)
        pt_utm = pt_gdf.iloc[0]
        
        nearest_idx = self.plat_tree.nearest(pt_utm)
        nearest_geom = self.plats_utm.geometry.iloc[nearest_idx]
        dist_m = float(pt_utm.distance(nearest_geom))
        
        row = self.plats_wgs84.iloc[nearest_idx].to_dict()
        row["distance_meters"] = dist_m
        return row, dist_m


def load_and_sanitize_ais(
    ais_path: str,
    time_window: TimeWindow,
    spatial_bbox: Optional[Tuple[float, float, float, float]] = None,
    max_speed_knots: float = 45.0,
    sentinel_speed: float = 102.3
) -> gpd.GeoDataFrame:
    if ais_path.endswith(".parquet"):
        df = pd.read_parquet(ais_path)
    else:
        df = pd.read_csv(ais_path)
        
    df.columns = [c.lower().strip() for c in df.columns]
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    
    t_start = pd.Timestamp(time_window.buffered_start)
    t_end = pd.Timestamp(time_window.buffered_end)
    df = df[(df["timestamp"] >= t_start) & (df["timestamp"] <= t_end)].copy()
    
    if spatial_bbox is not None:
        min_lon, min_lat, max_lon, max_lat = spatial_bbox
        df = df[
            (df["longitude"] >= min_lon) & (df["longitude"] <= max_lon) &
            (df["latitude"] >= min_lat) & (df["latitude"] <= max_lat)
        ].copy()
        
    speed_col = "speed_knots" if "speed_knots" in df.columns else ("sog" if "sog" in df.columns else None)
    if speed_col:
        df[speed_col] = df[speed_col].replace(sentinel_speed, np.nan)
        df.loc[df[speed_col] > max_speed_knots, speed_col] = np.nan
        df["speed_sanitized"] = df[speed_col]
    else:
        df["speed_sanitized"] = np.nan
        
    course_col = "course_deg" if "course_deg" in df.columns else ("cog" if "cog" in df.columns else None)
    if course_col:
        df.loc[(df[course_col] < 0) | (df[course_col] > 360), course_col] = np.nan
        df["course_sanitized"] = df[course_col]
    else:
        df["course_sanitized"] = np.nan
        
    df = df.drop_duplicates(subset=["mmsi", "timestamp"]).copy()
    df = df.sort_values(by=["mmsi", "timestamp"]).reset_index(drop=True)
    
    geometry = [Point(xy) for xy in zip(df["longitude"], df["latitude"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    return gdf


def load_infrastructure(
    pipelines_geojson_path: str,
    platforms_geojson_path: str,
    origin_centroid: Point,
    search_radius_meters: float = 10000.0,
    metric_crs: str = GOM_UTM_CRS
) -> InfrastructureIndex:
    cent_gdf = gpd.GeoSeries([origin_centroid], crs="EPSG:4326").to_crs(metric_crs)
    search_circle_utm = cent_gdf.iloc[0].buffer(search_radius_meters)
    search_circle_wgs84 = gpd.GeoSeries([search_circle_utm], crs=metric_crs).to_crs("EPSG:4326").iloc[0]
    
    if os.path.exists(pipelines_geojson_path):
        pipes = gpd.read_file(pipelines_geojson_path)
        if pipes.crs != "EPSG:4326":
            pipes = pipes.to_crs("EPSG:4326")
        local_pipes = pipes[pipes.intersects(search_circle_wgs84)].copy()
    else:
        local_pipes = gpd.GeoDataFrame(crs="EPSG:4326")
        
    if os.path.exists(platforms_geojson_path):
        plats = gpd.read_file(platforms_geojson_path)
        if plats.crs != "EPSG:4326":
            plats = plats.to_crs("EPSG:4326")
        local_plats = plats[plats.intersects(search_circle_wgs84)].copy()
    else:
        local_plats = gpd.GeoDataFrame(crs="EPSG:4326")
        
    return InfrastructureIndex(local_pipes, local_plats, metric_crs=metric_crs)

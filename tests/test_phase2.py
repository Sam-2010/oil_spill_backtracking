"""
test_phase2.py
--------------
Unit and verification test for Phase 2:
1. Tests morphology analysis on the benchmark MV Rubymar GeoJSON input.
2. Tests the fallback handler on the point-only input and confirms the warning message.
"""

import json
from src.morphology import SlickMorphologyAnalyzer

def run_tests():
    print("=" * 70)
    print("RUNNING PHASE 2 TESTS: MORPHOLOGY ENGINE & FALLBACK HANDLER")
    print("=" * 70)

    analyzer = SlickMorphologyAnalyzer(horizontal_diffusivity_m2s=10.0)

    # -------------------------------------------------------------
    # Test 1: Benchmark MV Rubymar GeoJSON Polygon
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Benchmark MV Rubymar GeoJSON...")
    result_poly = analyzer.analyze("inputs/rubymar_detection.geojson")

    assert result_poly["has_polygon"] is True, "Expected has_polygon to be True"
    assert result_poly["fallback_used"] is False, "Expected fallback_used to be False"
    assert result_poly["warning"] is None, "Expected warning to be None"
    
    morph = result_poly["morphology"]
    assert morph["length_km"] > 20.0, f"Expected length > 20km, got {morph['length_km']:.1f}km"
    assert morph["head_width_m"] < morph["tail_width_m"], "Expected head_width < tail_width"
    
    window = result_poly["estimated_origin_window_utc"]
    print(f" -> Result: Slick Length = {morph['length_km']:.2f} km")
    print(f" -> Result: W_head = {morph['head_width_m']:.0f} m, W_tail = {morph['tail_width_m']:.0f} m")
    print(f" -> Result: Calculated Elapsed Age = {morph['calculated_elapsed_hours']:.1f} hours")
    print(f" -> Result: Origin Time Window = {window['start']} to {window['end']}")
    print(" -> TEST 1 PASSED! [OK]")

    # -------------------------------------------------------------
    # Test 2: Fallback Point Input
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Fallback Point Input (No Polygon)...")
    result_fallback = analyzer.analyze("inputs/fallback_point.json")

    assert result_fallback["has_polygon"] is False, "Expected has_polygon to be False"
    assert result_fallback["fallback_used"] is True, "Expected fallback_used to be True"
    assert result_fallback["warning"] is not None, "Expected warning message to be populated"
    assert "[WARNING] No polygon geometry detected" in result_fallback["warning"], "Warning text missing expected prefix"
    
    print(f" -> Warning Captured: {result_fallback['warning']}")
    print(f" -> Evaluated Horizon: {result_fallback['max_backtrack_hours']} hours")
    print(" -> TEST 2 PASSED! [OK]")

    print("\n" + "=" * 70)
    print("ALL PHASE 2 TESTS COMPLETED SUCCESSFULLY! [OK]")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()

"""
generate_report.py
------------------
CLI utility to generate a publication-grade, court-admissible forensic report
(Markdown and PDF formats) combining Upstream Backtracking and Downstream AIS Attribution.
"""

import os
import sys
import argparse
from pathlib import Path
from src.reporting.report_generator import generate_forensic_report

def main():
    parser = argparse.ArgumentParser(description="Generate Comprehensive Forensic Investigation Report (MD & PDF)")
    parser.add_argument("--incident", choices=["taylor_energy", "main_pass"], default="taylor_energy", help="Preset incident name")
    parser.add_argument("--dir", default=None, help="Explicit incident output directory (overrides --incident)")
    parser.add_argument("--name", default="forensic_investigation_report", help="Base filename for generated report")
    args = parser.parse_args()

    if args.dir:
        target_dir = args.dir
    else:
        target_dir = f"outputs/{args.incident}"

    if not os.path.exists(target_dir):
        print(f"[ERROR] Target directory does not exist: {target_dir}")
        sys.exit(1)

    print("=" * 80)
    print("GENERATING COMPREHENSIVE FORENSIC INVESTIGATION REPORT")
    print(f"Target Directory: {os.path.abspath(target_dir)}")
    print("=" * 80)

    try:
        results = generate_forensic_report(target_dir, output_basename=args.name)
        print("\n>>> [SUCCESS] Forensic Reports Successfully Generated:")
        print(f"  Markdown Document: file:///{results['markdown'].replace(os.sep, '/')}")
        print(f"  HTML Print Master: file:///{results['html'].replace(os.sep, '/')}")
        print(f"  Compiled PDF:      file:///{results['pdf'].replace(os.sep, '/')}")
        print("=" * 80)
    except Exception as e:
        print(f"\n[ERROR] Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

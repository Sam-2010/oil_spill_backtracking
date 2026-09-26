"""
download_ais_resilient.py
-------------------------
Downloads the NOAA Marine Cadastre AIS archive using chunked HTTP Range requests
with automatic retries, ensuring full completion without TLS drops.
Then extracts all AIS pings for the Main Pass / Mississippi Delta bounding box.
"""

import os
import sys
import time
import urllib.request
from pathlib import Path

# Add project root
sys.path.insert(0, os.path.abspath("."))
import extract_main_pass_ais

URL = "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/AIS_2023_11_16.zip"
TARGET_FILE = Path("data/ais/AIS_2023_11_16.zip")
TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
TOTAL_SIZE = 307930042
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB per chunk

def download_file():
    current_size = TARGET_FILE.stat().st_size if TARGET_FILE.exists() else 0

    print("=" * 65)
    print("RESILIENT NOAA AIS DOWNLOADER (HTTP RANGE CHUNKS)")
    print(f" -> Target URL: {URL}")
    print(f" -> Total File Size: {TOTAL_SIZE / (1024*1024):.1f} MB")
    print(f" -> Existing bytes:  {current_size / (1024*1024):.1f} MB ({current_size:,} bytes)")
    print("=" * 65)

    if current_size >= TOTAL_SIZE:
        print(" -> File already fully downloaded! [OK]")
        return

    while current_size < TOTAL_SIZE:
        start_byte = current_size
        end_byte = min(current_size + CHUNK_SIZE - 1, TOTAL_SIZE - 1)
        expected_len = end_byte - start_byte + 1

        success = False
        for attempt in range(1, 11):
            try:
                req = urllib.request.Request(
                    URL,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                        'Range': f'bytes={start_byte}-{end_byte}'
                    }
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status not in (200, 206):
                        raise RuntimeError(f"Unexpected status: {resp.status}")
                    data = resp.read()
                    if len(data) != expected_len:
                        raise RuntimeError(f"Short read: got {len(data)}, expected {expected_len}")

                    with open(TARGET_FILE, 'ab' if start_byte > 0 else 'wb') as f:
                        f.write(data)

                    current_size += len(data)
                    pct = (current_size / TOTAL_SIZE) * 100
                    print(f" -> Downloaded: {current_size / (1024*1024):.1f} MB / {TOTAL_SIZE / (1024*1024):.1f} MB ({pct:.1f}%) [Chunk {start_byte//CHUNK_SIZE + 1}]")
                    success = True
                    break
            except Exception as e:
                print(f"    [Warning] Chunk {start_byte}-{end_byte} attempt {attempt}/10 failed: {e}. Retrying in 2s...")
                time.sleep(2)

        if not success:
            raise RuntimeError(f"Failed to download chunk {start_byte}-{end_byte} after 10 attempts.")

    print("\n -> Full archive download complete! [100% OK]")

def main():
    download_file()
    print("\nProceeding to filter AIS data for Main Pass...")
    extract_main_pass_ais.main()

if __name__ == "__main__":
    main()

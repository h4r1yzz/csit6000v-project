"""Publish the Vite build (including model/WASM) through Vercel's static CDN."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
built = root / "frontend" / "dist"
for asset in ("index.html", "models/pose_landmarker_lite.task", "mediapipe/wasm/vision_wasm_internal.wasm"):
    if not (built / asset).is_file():
        raise SystemExit(f"Required deployment asset missing: {asset}")
shutil.copytree(built, root / "public", dirs_exist_ok=True)
print("Prepared Vercel static assets, including MediaPipe model and WASM.")

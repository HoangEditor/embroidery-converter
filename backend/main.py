"""
Embroidery File Converter API
Upload 1 file → Convert to selected formats → ZIP (includes original file)
Files auto-deleted after 10 minutes.
"""
import os
import uuid
import shutil
import zipfile
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pyembroidery as pe

# ── Config ──────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
FILE_LIFETIME_MINUTES = 10
CLEANUP_INTERVAL = 60

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── All writable formats with metadata ──────────────
ALL_FORMATS = []
for item in pe.supported_formats():
    ext = item["extension"]
    writer = item.get("writer")
    if writer is not None:
        ALL_FORMATS.append({
            "extension": ext,
            "name": ext.upper(),
            "description": item.get("description", ""),
            "category": item.get("category", "embroidery"),
        })

# Sort by popularity/common usage
FORMAT_PRIORITY = ["dst", "pes", "jef", "exp", "pec", "vp3", "xxx", "u01", "tbf"]
ALL_FORMATS.sort(key=lambda f: (
    FORMAT_PRIORITY.index(f["extension"]) if f["extension"] in FORMAT_PRIORITY else 99,
    f["extension"]
))

DEFAULT_FORMATS = FORMAT_PRIORITY.copy()

# ── Background cleanup ──────────────────────────────
async def cleanup_expired_files():
    while True:
        try:
            now = datetime.now()
            for folder in UPLOAD_DIR.iterdir():
                if folder.is_dir():
                    meta_file = folder / ".meta"
                    if meta_file.exists():
                        created_at = datetime.fromisoformat(meta_file.read_text().strip())
                        if now - created_at > timedelta(minutes=FILE_LIFETIME_MINUTES):
                            shutil.rmtree(folder)
                            print(f"[CLEANUP] Deleted expired: {folder.name}")
        except Exception as e:
            print(f"[CLEANUP] Error: {e}")
        await asyncio.sleep(CLEANUP_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_expired_files())
    print(f"[STARTUP] Cleanup task started (TTL: {FILE_LIFETIME_MINUTES}min)")
    yield
    task.cancel()


# ── App ─────────────────────────────────────────────
app = FastAPI(
    title="Embroidery File Converter - Free Online Tool",
    description="Convert embroidery files between all major formats. Free, no signup. DST, PES, JEF, EXP, PEC, VP3 and more.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ──────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "formats": len(ALL_FORMATS)}


@app.get("/api/formats")
async def list_formats():
    """Return all supported output formats with metadata."""
    return {
        "formats": ALL_FORMATS,
        "default_formats": DEFAULT_FORMATS,
        "total": len(ALL_FORMATS),
    }


@app.post("/api/convert")
async def convert_file(
    file: UploadFile = File(...),
    formats: Optional[str] = Form(None),
):
    """
    Upload embroidery file → convert to selected formats → ZIP with original file.
    
    - `formats`: comma-separated list of extensions (e.g. "dst,pes,jef").
      If not provided, defaults to all 9 major formats.
    - Original file is always included in the ZIP.
    - Files auto-deleted after 10 minutes.
    """
    # Parse requested formats
    if formats:
        requested = [f.strip().lower().lstrip(".") for f in formats.split(",") if f.strip()]
        # Validate all requested formats
        valid_exts = {f["extension"] for f in ALL_FORMATS}
        invalid = [f for f in requested if f not in valid_exts]
        if invalid:
            raise HTTPException(400, f"Unsupported format(s): {', '.join(invalid)}")
        output_formats = requested
    else:
        output_formats = DEFAULT_FORMATS

    # Validate file extension
    original_ext = Path(file.filename).suffix.lower().lstrip(".")
    if not original_ext:
        raise HTTPException(400, "Could not determine file format from extension")

    # Create session folder
    session_id = uuid.uuid4().hex[:12]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    input_path = session_dir / file.filename
    try:
        content = await file.read()
        input_path.write_bytes(content)
    except Exception as e:
        shutil.rmtree(session_dir)
        raise HTTPException(500, f"Failed to save uploaded file: {e}")

    # Read embroidery pattern
    try:
        pattern = pe.read(str(input_path))
    except Exception as e:
        shutil.rmtree(session_dir)
        raise HTTPException(400, f"Unsupported or invalid embroidery file: {e}")

    if pattern is None or pattern.count_stitches() == 0:
        shutil.rmtree(session_dir)
        raise HTTPException(400, "File contains no embroidery data or is empty")

    # Convert to selected formats
    converted_files = []
    skipped = []
    base_name = Path(file.filename).stem
    for fmt in output_formats:
        if fmt == original_ext:
            # Same format as input — skip conversion, use original
            converted_files.append(input_path)
            continue
        try:
            out_path = session_dir / f"{base_name}.{fmt}"
            pe.write(pattern, str(out_path))
            converted_files.append(out_path)
        except Exception as e:
            skipped.append(fmt)
            print(f"[WARN] Could not convert to .{fmt}: {e}")

    if not converted_files:
        shutil.rmtree(session_dir)
        raise HTTPException(500, "Failed to convert to any format")

    # Create ZIP — always include original file
    zip_filename = f"{base_name}_all_formats.zip"
    zip_path = session_dir / zip_filename
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Original file (always included)
        zf.write(input_path, file.filename)
        # Converted files (skip if it's the same as original)
        for f in converted_files:
            if f != input_path:
                zf.write(f, f.name)

    # Metadata for cleanup
    meta_file = session_dir / ".meta"
    meta_file.write_text(datetime.now().isoformat())

    expiry_time = datetime.now() + timedelta(minutes=FILE_LIFETIME_MINUTES)
    return {
        "session_id": session_id,
        "download_url": f"/api/download/{session_id}/{zip_filename}",
        "filename": zip_filename,
        "input_format": original_ext.upper(),
        "output_formats": [f.suffix.upper().lstrip(".") for f in converted_files if f != input_path],
        "original_included": True,
        "stitch_count": pattern.count_stitches(),
        "zip_size_bytes": zip_path.stat().st_size,
        "expires_at": expiry_time.isoformat(),
        "expires_in_minutes": FILE_LIFETIME_MINUTES,
        "skipped_formats": skipped,
    }


@app.get("/api/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    file_path = UPLOAD_DIR / session_id / filename
    if not file_path.exists():
        raise HTTPException(404, "File expired or not found. Files are kept for 10 minutes.")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/zip",
    )


# ── Frontend ────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>Embroidery Converter API is running</h1>"


@app.get("/sitemap.xml")
async def sitemap():
    path = STATIC_DIR / "sitemap.xml"
    if path.exists():
        return Response(content=path.read_text(), media_type="application/xml")
    return Response(status_code=404)


@app.get("/robots.txt")
async def robots():
    path = STATIC_DIR / "robots.txt"
    if path.exists():
        return Response(content=path.read_text(), media_type="text/plain")
    return Response(status_code=404)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from process_workbook import process_workbook

load_dotenv()

APP_API_KEY = os.getenv("APP_API_KEY", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
WORK_DIR = Path(os.getenv("WORK_DIR", "/tmp/weekly_property_workbooks"))
IN_DIR = WORK_DIR / "incoming"
OUT_DIR = WORK_DIR / "processed"
IN_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Smarty-Only Weekly Property Workbook Tool")


class ProcessRequest(BaseModel):
    file_url: HttpUrl
    sender_email: str | None = None
    original_subject: str | None = None
    original_filename: str | None = None
    sheet_name: str | None = None
    start_row: int = 2
    city_column: str | None = None


def safe_excel_filename(filename: str | None, fallback: str) -> str:
    """Return a safe Excel filename while preserving the user-visible name.

    Zapier/Gmail can pass the original attachment filename separately from the
    file object. We save the output with that filename so the returned attachment
    keeps the same name. Path separators/control characters are removed for safety.
    """
    raw = (filename or fallback).strip()
    raw = Path(raw).name.replace('\\', '_').replace('/', '_')
    raw = ''.join(ch for ch in raw if ch.isprintable()).strip()
    if not raw:
        raw = fallback
    if not raw.lower().endswith('.xlsx'):
        raw += '.xlsx'
    return raw


def require_api_key(x_api_key: str | None):
    if APP_API_KEY and x_api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def download_file(url: str, path: Path):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    path.write_bytes(response.content)


@app.get("/health")
def health():
    return {"ok": True, "mode": "smarty_only"}


@app.post("/process")
def process(req: ProcessRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    job_id = uuid.uuid4().hex
    job_out_dir = OUT_DIR / job_id
    job_out_dir.mkdir(parents=True, exist_ok=True)

    input_path = IN_DIR / f"{job_id}.xlsx"
    output_filename = safe_excel_filename(req.original_filename, f"{job_id}_updated.xlsx")
    output_path = job_out_dir / output_filename

    try:
        download_file(str(req.file_url), input_path)
        stats = process_workbook(input_path, output_path, sheet_name=req.sheet_name, start_row=req.start_row, city_column=req.city_column, verbose=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    encoded_filename = quote(output_path.name)
    download_url = urljoin(PUBLIC_BASE_URL.rstrip("/") + "/", f"files/{job_id}/{encoded_filename}")
    return {
        "job_id": job_id,
        "download_url": download_url,
        "filename": output_path.name,
        "sender_email": req.sender_email,
        "original_subject": req.original_subject,
        "original_filename": req.original_filename,
        "stats": asdict(stats),
    }


@app.get("/files/{job_id}/{filename}")
def get_job_file(job_id: str, filename: str):
    safe_name = safe_excel_filename(filename, "updated_workbook.xlsx")
    path = OUT_DIR / job_id / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=safe_name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/files/{filename}")
def get_file(filename: str):
    # Legacy route for older links created by previous versions.
    safe_name = safe_excel_filename(filename, "updated_workbook.xlsx")
    path = OUT_DIR / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=safe_name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

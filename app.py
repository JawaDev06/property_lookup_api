from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin

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
    sheet_name: str | None = None
    start_row: int = 2
    city_column: str | None = None


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
    input_path = IN_DIR / f"{job_id}.xlsx"
    output_path = OUT_DIR / f"{job_id}_updated.xlsx"

    try:
        download_file(str(req.file_url), input_path)
        stats = process_workbook(input_path, output_path, sheet_name=req.sheet_name, start_row=req.start_row, city_column=req.city_column, verbose=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    download_url = urljoin(PUBLIC_BASE_URL.rstrip("/") + "/", f"files/{output_path.name}")
    return {
        "job_id": job_id,
        "download_url": download_url,
        "filename": output_path.name,
        "sender_email": req.sender_email,
        "original_subject": req.original_subject,
        "stats": asdict(stats),
    }


@app.get("/files/{filename}")
def get_file(filename: str):
    path = OUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

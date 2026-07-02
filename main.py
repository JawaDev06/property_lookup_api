import asyncio
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from router import lookup_property
from workbook import process_workbook

app = FastAPI(title="Property Lookup API", version="11.0.0")

@app.get("/")
def root():
    return {"status": "ok", "service": "Property Lookup API v11", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/lookup-test")
async def lookup_test(address: str):
    result = await asyncio.to_thread(lookup_property, address)
    return result.to_dict()

@app.post("/process-workbook")
async def process_workbook_endpoint(file: UploadFile = File(...), overwrite: bool = True):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        input_path = tmp / file.filename
        output_path = tmp / f"{Path(file.filename).stem}_UPDATED.xlsx"
        input_path.write_bytes(await file.read())
        summary = await asyncio.to_thread(process_workbook, input_path, output_path, overwrite)
        return FileResponse(output_path, filename=output_path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

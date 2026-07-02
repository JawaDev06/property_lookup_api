from __future__ import annotations
import argparse, time
from pathlib import Path
from property_scraper.workbook import process_folder


def default_base() -> Path:
    # If script is in .../Property Details Automation/Script/official_property_scraper,
    # default to the parent Property Details Automation folder when it exists.
    here = Path.cwd().resolve()
    for parent in [here] + list(here.parents):
        if parent.name.lower() == "property details automation":
            return parent
    return here


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Official modular Virginia property assessor workbook updater")
    p.add_argument("--base", default=None, help="Base folder containing Input, Output, Processed, Logs")
    p.add_argument("--input", default=None, help="Input folder. Defaults to BASE/Input")
    p.add_argument("--output", default=None, help="Output folder. Defaults to BASE/Output")
    p.add_argument("--processed", default=None, help="Processed folder. Defaults to BASE/Processed")
    p.add_argument("--logs", default=None, help="Logs folder. Defaults to BASE/Logs")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing F/N/O/P/Q/R/S/T/U values")
    p.add_argument("--headed", action="store_true", help="Show browser for browser-only sites")
    p.add_argument("--watch", action="store_true", help="Keep checking Input folder repeatedly")
    p.add_argument("--interval", type=int, default=300, help="Watch interval in seconds; default 300")
    p.add_argument("--dry-run", action="store_true", help="Do not save or move files")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    base = Path(args.base).expanduser() if args.base else default_base()
    input_dir = Path(args.input).expanduser() if args.input else base / "Input"
    output_dir = Path(args.output).expanduser() if args.output else base / "Output"
    processed_dir = Path(args.processed).expanduser() if args.processed else base / "Processed"
    logs_dir = Path(args.logs).expanduser() if args.logs else base / "Logs"

    def once():
        outs = process_folder(input_dir, output_dir, processed_dir, logs_dir, overwrite=args.overwrite, headed=args.headed, dry_run=args.dry_run)
        if outs:
            print("Processed files:")
            for o in outs:
                print(f" - {o}")
        else:
            print(f"No .xlsx files found in {input_dir}")

    if args.watch:
        print(f"Watching {input_dir}. Press Ctrl+C to stop.")
        while True:
            once()
            time.sleep(args.interval)
    else:
        once()

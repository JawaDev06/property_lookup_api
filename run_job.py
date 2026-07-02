import argparse
import json
from workbook import process_input_folder

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Excel property workbooks from Input folder.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing values in F/N/O/P/Q/R/S/T.")
    parser.add_argument("--no-move", action="store_true", help="Do not move originals to Processed.")
    args = parser.parse_args()
    summary = process_input_folder(overwrite=args.overwrite, move_processed=not args.no_move)
    print(json.dumps(summary, indent=2))

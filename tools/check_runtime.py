"""Check every web feature's runtime dependencies without loading ML weights."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Local_Rag" / "rag"))
from runtime import runtime_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--evaluation", action="store_true", help="Also check optional evaluation packages")
    args = parser.parse_args()
    report = runtime_report(include_evaluation=args.evaluation)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Python: {sys.executable}")
        for name, feature in report["features"].items():
            print(f"{'OK' if feature['ready'] else 'MISSING/BROKEN'}: {name}")
            for issue in feature["issues"]:
                print(f"  {issue}")
        if not report["ready"]:
            print("Repair with ./setup.sh using this project's virtual environment.")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

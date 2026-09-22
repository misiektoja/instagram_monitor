"""Apply CodeQL source suppressions before uploading SARIF to GitHub."""

import argparse
import json
from pathlib import Path


# Removes accepted source suppressions while retaining all other results and analysis metadata
def filter_source_suppressions(report):
    if report.get("version") != "2.1.0" or not isinstance(report.get("runs"), list) or not report["runs"]:
        raise ValueError("Expected a SARIF 2.1.0 report with at least one run")
    removed = 0
    for run in report["runs"]:
        if run["tool"]["driver"]["name"] not in ("CodeQL", "CodeQL command-line toolchain") or "results" not in run:
            continue
        retained = []
        for result in run["results"]:
            suppressed = any(suppression.get("kind") == "inSource" and suppression.get("status", "accepted") == "accepted" for suppression in (result.get("suppressions") or []))
            if suppressed:
                removed += 1
            else:
                retained.append(result)
        run["results"] = retained
    return removed


# Writes a filtered copy of one CodeQL report and reports how many source suppressions were applied
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("Source and destination must differ to preserve the original report")
    report = json.loads(args.source.read_text(encoding="utf-8"))
    removed = filter_source_suppressions(report)
    args.destination.write_text(json.dumps(report) + "\n", encoding="utf-8")
    print(f"Applied {removed} CodeQL source suppressions")


if __name__ == "__main__":
    main()

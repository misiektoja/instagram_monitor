"""CodeQL upload filtering keeps unsuppressed security findings reportable."""

import copy
import json
import re
import tokenize
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FILTER_SCRIPT = PROJECT_ROOT / ".github" / "scripts" / "filter_codeql_sarif.py"


@pytest.mark.parametrize("tool_name", ["CodeQL", "CodeQL command-line toolchain"])
# Keeps unsuppressed findings and metadata in reports from both CodeQL tool names
def test_filter_keeps_unsuppressed_results_and_metadata(tmp_path, tool_name):
    suppressions = [
        None,
        [],
        [{"kind": "inSource"}],
        [{"kind": "inSource", "status": "accepted"}],
        [{"kind": "inSource", "status": "rejected"}],
        [{"kind": "inSource", "status": "underReview"}],
        [{"kind": "external", "status": "accepted"}],
        [{"status": "accepted"}],
        [{"kind": "inSource", "status": None}],
    ]
    results = [{
        "ruleId": "py/clear-text-logging-sensitive-data",
        "message": {"text": str(index)},
        "suppressions": value,
        "partialFingerprints": {"primaryLocationLineHash": str(index)},
    } for index, value in enumerate(suppressions)]
    results.append({"ruleId": "py/clear-text-logging-sensitive-data", "message": {"text": "No suppression property"}})
    report = {"version": "2.1.0", "runs": [
        {"tool": {"driver": {"name": tool_name}}, "automationDetails": {"id": "/language:python/"}, "results": results},
        {"tool": {"driver": {"name": "CodeQL"}}, "results": [results[2]]},
        {"tool": {"driver": {"name": "CodeQL"}}},
        {"tool": {"driver": {"name": "Other scanner"}}, "results": [results[2]]},
    ]}
    expected = copy.deepcopy(report)
    expected["runs"][0]["results"] = [result for index, result in enumerate(results) if index not in (2, 3)]
    expected["runs"][1]["results"] = []
    source = tmp_path / "input.sarif"
    destination = tmp_path / "output.sarif"
    original = json.dumps(report)
    source.write_text(original, encoding="utf-8")

    completed = subprocess.run([sys.executable, str(FILTER_SCRIPT), str(source), str(destination)], check=True, capture_output=True, text=True)

    assert json.loads(destination.read_text(encoding="utf-8")) == expected
    assert source.read_text(encoding="utf-8") == original
    assert completed.stdout == "Applied 3 CodeQL source suppressions\n"


@pytest.mark.parametrize("content", ["not JSON", "{}", '{"version": "2.1.0", "runs": []}', '{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "CodeQL"}}, "results": null}]}'])
# Rejects invalid reports before creating an uploadable file
def test_filter_fails_before_upload_on_invalid_report(tmp_path, content):
    source = tmp_path / "input.sarif"
    destination = tmp_path / "output.sarif"
    source.write_text(content, encoding="utf-8")

    completed = subprocess.run([sys.executable, str(FILTER_SCRIPT), str(source), str(destination)], capture_output=True, text=True)

    assert completed.returncode != 0
    assert not destination.exists()


# Prevents accidental replacement of the original analysis evidence
def test_filter_preserves_original_report_when_paths_match(tmp_path):
    source = tmp_path / "input.sarif"
    original = '{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "CodeQL"}}}]}'
    source.write_text(original, encoding="utf-8")

    completed = subprocess.run([sys.executable, str(FILTER_SCRIPT), str(source), str(source)], capture_output=True, text=True)

    assert completed.returncode != 0
    assert source.read_text(encoding="utf-8") == original


# Uploads only the filtered report after successful analysis and filtering
def test_workflow_filters_before_upload():
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["analyze"]["steps"]
    initialize = next(step for step in steps if step.get("uses", "").startswith("github/codeql-action/init@"))
    analyze = next(step for step in steps if step.get("uses", "").startswith("github/codeql-action/analyze@"))
    apply = next(step for step in steps if "filter_codeql_sarif.py" in step.get("run", ""))
    upload = next(step for step in steps if step.get("uses", "").startswith("github/codeql-action/upload-sarif@"))

    assert initialize["with"]["queries"] == "security-extended"
    assert initialize["with"]["packs"] == "codeql/python-queries:AlertSuppression.ql"
    assert analyze["with"]["upload"] == "failure-only"
    assert apply["run"] == "python .github/scripts/filter_codeql_sarif.py sarif-results/python.sarif sarif-results/python-filtered.sarif"
    assert analyze["with"]["output"] == "sarif-results"
    assert upload["with"]["sarif_file"] == "sarif-results/python-filtered.sarif"
    assert upload["with"]["category"] == analyze["with"]["category"]
    assert steps.index(analyze) < steps.index(apply) < steps.index(upload)
    assert "if" not in upload
    assert not any(step.get("continue-on-error") for step in (analyze, apply, upload))


# Keeps each suppression scoped to one query ID on the line immediately before the affected code
def test_source_suppressions_use_individual_rule_ids():
    annotations = []
    for source in PROJECT_ROOT.glob("*.py"):
        lines = source.read_text(encoding="utf-8").splitlines()
        with tokenize.open(source) as stream:
            comments = [token for token in tokenize.generate_tokens(stream.readline) if token.type == tokenize.COMMENT]
        for comment in comments:
            for rule_id in re.findall(r"\bcodeql\[([^\]]*)\]", comment.string):
                assert re.fullmatch(r"py/[a-z0-9/-]+", rule_id), f"{source.name}:{comment.start[0]}: use a separate codeql annotation for each rule"
                assert not lines[comment.start[0] - 1][:comment.start[1]].strip()
                assert lines[comment.end[0]].strip() and not lines[comment.end[0]].lstrip().startswith("#")
                annotations.append(rule_id)
    assert annotations

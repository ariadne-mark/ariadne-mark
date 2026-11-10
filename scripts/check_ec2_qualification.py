"""Read GitHub qualification records only; no SDK/media tests run on this host."""
import json
import os
import re
import sys
import urllib.request

REPO = "ariadne-mark/ariadne-mark"
sha = os.environ["EXPECTED_SHA"]
if not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit("Expected a full reviewed SHA")
if os.environ.get("GITHUB_REPOSITORY", REPO) != REPO:
    raise SystemExit("Unexpected repository")

def get(path):
    request = urllib.request.Request("https://api.github.com/" + path, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

path = f"repos/{REPO}/actions/workflows/scaffold.yml/runs?event=workflow_dispatch&head_sha={sha}&status=success&per_page=100"
for run in get(path)["workflow_runs"]:
    if (run["head_sha"] != sha or run["event"] != "workflow_dispatch"
            or run["conclusion"] != "success" or run["actor"]["login"] != "Genesius001"):
        continue
    jobs = get(f"repos/{REPO}/actions/runs/{run['id']}/jobs?filter=latest&per_page=100")["jobs"]
    qualified = False
    for job in jobs:
        if job["name"] != "EC2 release qualification" or job["conclusion"] != "success":
            continue
        passed = {step["name"] for step in job["steps"] if step["conclusion"] == "success"}
        required = {"Require the exact reviewed SHA", "Retain evidence from this revision"}
        execution = {"Qualify source build on EC2", "Qualify unchanged published package on EC2"}
        if required <= passed and execution & passed:
            qualified = True
            break
    if not qualified:
        continue
    artifacts = get(f"repos/{REPO}/actions/runs/{run['id']}/artifacts?per_page=100")["artifacts"]
    artifact = next((a for a in artifacts if a["name"] == "alpha-candidate-" + sha and not a["expired"]), None)
    if not artifact:
        continue
    print(json.dumps({"ok": True, "reviewed_sha": sha, "qualified_run": run["html_url"],
                      "artifact_id": artifact["id"], "artifact_name": artifact["name"],
                      "scope": "GitHub evidence gate only. SDK/media tests ran on the owned EC2 runner."}, indent=2))
    sys.exit(0)

raise SystemExit("No successful maintainer EC2 qualification with retained evidence for this exact SHA. Dispatch qualification after reviewing the revision, then rerun this PR check.")

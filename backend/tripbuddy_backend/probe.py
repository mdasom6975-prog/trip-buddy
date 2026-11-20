"""CLI for the offline integration gate."""
import argparse
import json
from pathlib import Path
import subprocess
from .bridge import BridgeError, probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--engine-python", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checks = []
    try:
        for scenario in ("course", "clarification", "abstain", "edit", "failure"):
            events = probe(args.engine_root, args.engine_python, scenario)
            final = events[-1]
            if final["type"] != "completed" or final["network_attempts"] or final["streamlit_imported"]:
                raise BridgeError("probe_acceptance_failed")
            checks.append({"scenario": scenario, "answer_kinds": [a["kind"] for a in final["answers"]],
                "nodes": [e["node"] for e in events if e["type"] == "progress"],
                "violations": [s["violations"] for s in final["states"]], "network_attempts": final["network_attempts"],
                "streamlit_imported": final["streamlit_imported"], "persistent_storage": final["persistent_storage"]})
    except BridgeError as error:
        print(json.dumps({"ok": False, "code": str(error)}))
        return 1
    revision = subprocess.run(["git", "-C", str(args.engine_root), "rev-parse", "HEAD"], capture_output=True, text=True)
    report = {"ok": True, "source": "fixture", "engine_revision": revision.stdout.strip() if not revision.returncode else None,
              "production_ready": False, "checks": checks}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

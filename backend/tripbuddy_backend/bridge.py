"""Explicit local-development bridge, without source copying or sys.path changes."""
import json
import os
from pathlib import Path
import subprocess


class BridgeError(RuntimeError):
    """Safe transport error; no child output or credentials included."""


def probe(engine_root: Path, engine_python: Path, scenario="course", *, timeout=30):
    root, python = engine_root.resolve(), engine_python.absolute()
    if not (root / "graph/runtime.py").is_file():
        raise BridgeError("engine_source_missing")
    if not python.is_file():
        raise BridgeError("engine_python_missing")
    if scenario not in {"course", "clarification", "abstain", "edit", "failure"}:
        raise BridgeError("unknown_scenario")
    worker = Path(__file__).with_name("probe_worker.py")
    command = [str(python), "-c", "import runpy,sys; runpy.run_path(sys.argv[1],run_name='__main__')", str(worker)]
    try:
        result = subprocess.run(command, cwd=root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "TOKENIZERS_PARALLELISM": "false"},
            input=json.dumps({"scenario": scenario}), text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise BridgeError("engine_timeout") from None
    except OSError:
        raise BridgeError("engine_launch_failed") from None
    if result.returncode:
        raise BridgeError("engine_process_failed")
    try:
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if not events or events[-1].get("type") not in {"completed", "failed"}:
            raise ValueError
        if any(not isinstance(e, dict) or e.get("id") != n for n, e in enumerate(events, 1)):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise BridgeError("engine_protocol_invalid") from None
    return events

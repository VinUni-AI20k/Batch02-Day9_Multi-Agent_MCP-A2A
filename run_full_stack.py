"""Run the full Stage 5 stack plus the HTML demo UI.

This launcher starts the registry, all agents, and the demo UI as child
processes, redirecting each service's stdout/stderr to `.stage5_logs/`.
It is suitable for local demos and single-container deployment.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
LOG_DIR = ROOT_DIR / ".stage5_logs"

SERVICES = [
    {"name": "registry", "module": "registry", "delay": 2},
    {"name": "tax", "module": "tax_agent", "delay": 0},
    {"name": "compliance", "module": "compliance_agent", "delay": 3},
    {"name": "law", "module": "law_agent", "delay": 3},
    {"name": "customer", "module": "customer_agent", "delay": 2},
    {"name": "demo_ui", "module": "demo_ui", "delay": 0},
]


def _python_executable() -> str:
    venv_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _start_service(python: str, service: dict[str, object]) -> subprocess.Popen:
    LOG_DIR.mkdir(exist_ok=True)
    out_path = LOG_DIR / f"{service['name']}.out.log"
    err_path = LOG_DIR / f"{service['name']}.err.log"

    out_file = open(out_path, "a", encoding="utf-8")
    err_file = open(err_path, "a", encoding="utf-8")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    process = subprocess.Popen(
        [python, "-m", str(service["module"])],
        cwd=ROOT_DIR,
        env=env,
        stdout=out_file,
        stderr=err_file,
    )
    return process


def main() -> None:
    python = _python_executable()
    processes: list[tuple[str, subprocess.Popen]] = []

    print("Starting full Legal Multi-Agent stack...")
    print(f"Logs directory: {LOG_DIR}")

    try:
        for service in SERVICES:
            process = _start_service(python, service)
            processes.append((str(service["name"]), process))
            print(f"Started {service['name']} (pid={process.pid})")
            delay = int(service.get("delay", 0))
            if delay > 0:
                time.sleep(delay)

        print("")
        print("Stack is launching.")
        print("UI: http://localhost:8008")
        print("Press Ctrl+C to stop all services.")

        while True:
            failed = [(name, proc.returncode) for name, proc in processes if proc.poll() is not None]
            if failed:
                name, code = failed[0]
                raise RuntimeError(f"Service '{name}' exited early with code {code}. Check .stage5_logs/{name}.err.log")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for _, process in reversed(processes):
            if process.poll() is None:
                process.terminate()

        deadline = time.time() + 10
        for _, process in reversed(processes):
            while process.poll() is None and time.time() < deadline:
                time.sleep(0.2)
            if process.poll() is None:
                process.kill()

        if os.name != "nt":
            signal.signal(signal.SIGTERM, signal.SIG_DFL)


if __name__ == "__main__":
    main()

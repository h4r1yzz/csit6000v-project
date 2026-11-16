#!/usr/bin/env python3
"""Start FitPilot's local API and UI; stop only the processes we start."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from tacc_connection import job_running, start_tunnel, wait_for_model

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PYTHON = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def stop(process: subprocess.Popen) -> None:
    """Terminate the owned process group, including Vite/Uvicorn children."""
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        elif process.poll() is None:
            process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()
    except ProcessLookupError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tacc-job", help="ID of a running FitPilot Qwen service job")
    parser.add_argument("--tcloud", default="tcloud", help="Path to the configured course SDK")
    parser.add_argument("--tacc-port", type=int, default=18000, help="Local SSH forwarding port")
    args = parser.parse_args()
    if args.tacc_job and (not args.tacc_job.isascii() or not args.tacc_job.isdecimal()):
        parser.error("--tacc-job must be a numeric job ID")
    if args.tacc_job and (not 1024 <= args.tacc_port <= 65535 or args.tacc_port in (5173, 8000)):
        parser.error("--tacc-port must be between 1024 and 65535 and separate from the app ports")

    if not PYTHON.exists():
        print("Create backend/.venv and install backend/requirements.txt first; see README.md.", file=sys.stderr)
        return 1
    if not (FRONTEND / "node_modules").is_dir():
        print("Install frontend dependencies first: cd frontend && npm ci", file=sys.stderr)
        return 1
    npm = shutil.which("npm")
    if not npm:
        print("Node.js 20+ and npm must be available on PATH.", file=sys.stderr)
        return 1

    api_command = [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    if (BACKEND / ".env").exists():
        api_command += ["--env-file", str(BACKEND / ".env")]
    ui_command = [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"]
    processes: list[subprocess.Popen] = []

    def interrupted(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        backend_env = os.environ.copy()
        sdk = None
        tunnel = None
        if args.tacc_job:
            sdk = shutil.which(args.tcloud)
            if not sdk:
                raise RuntimeError("Could not find tcloud. Use --tcloud with the SDK executable path.")
            print(f"Connecting to TACC Qwen job {args.tacc_job}…", flush=True)
            tunnel = start_tunnel(args.tacc_job, sdk, args.tacc_port)
            processes.append(tunnel)
            endpoint = f"http://127.0.0.1:{args.tacc_port}/v1"
            wait_for_model(tunnel, endpoint)
            bypass = ','.join(filter(None, (backend_env.get('no_proxy'), backend_env.get('NO_PROXY'), '127.0.0.1')))
            backend_env.update(QWEN_BASE_URL=endpoint, QWEN_MODEL="qwen3.8-27b",
                               LLM_BASE_URL="", LLM_API_KEY="", NO_PROXY=bypass, no_proxy=bypass)
        print("Starting FitPilot. UI: http://127.0.0.1:5173  API docs: http://127.0.0.1:8000/docs", flush=True)
        print("Press Ctrl+C to stop local services. Your SQLite database will be kept.", flush=True)
        for command, directory, env in ((api_command, BACKEND, backend_env), (ui_command, FRONTEND, None)):
            processes.append(subprocess.Popen(command, cwd=directory, env=env, start_new_session=(os.name == "posix")))
        next_job_check = time.monotonic() + 30
        while True:
            if tunnel and time.monotonic() >= next_job_check:
                try:
                    if not job_running(args.tacc_job, sdk):
                        print(f"TACC job {args.tacc_job} ended. FitPilot will use local rules.", file=sys.stderr)
                        stop(tunnel)
                except RuntimeError as error:
                    print(f"{error} Closing the TACC connection and keeping FitPilot open.", file=sys.stderr)
                    stop(tunnel)
                next_job_check = time.monotonic() + 30
            if tunnel and tunnel.poll() is not None:
                processes.remove(tunnel)
                tunnel = None
                print("TACC forwarding closed. The dashboard and pose tracking are still available.", file=sys.stderr)
            for process in processes:
                code = process.poll()
                if code is not None:
                    print(f"A local process exited ({code}); stopping the remaining processes.", file=sys.stderr)
                    return code or 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping FitPilot services…", flush=True)
        return 0
    except (OSError, RuntimeError) as error:
        print(f"Could not start development services: {error}", file=sys.stderr)
        return 1
    finally:
        # Ignore a second Ctrl+C while cleaning up our own children.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    raise SystemExit(main())

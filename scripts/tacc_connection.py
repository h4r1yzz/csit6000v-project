"""Connect the local backend to a running TACC Qwen job over SSH."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


def job_running(job_id: str, sdk: str) -> bool:
    try:
        result = subprocess.run([sdk, "ps", "-j", job_id], capture_output=True, timeout=20, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not check the status of TACC job {job_id}.") from exc
    rows = result.stdout.decode(errors="replace").replace("\x00", "").splitlines()
    return any(len(fields) >= 5 and fields[0] == job_id and fields[4] == "R"
               for fields in map(str.split, rows))


def service_address(job_id: str, sdk: str) -> tuple[str, int]:
    if not job_running(job_id, sdk):
        raise RuntimeError(f"TACC job {job_id} is not running. Check tcloud ps before connecting.")
    try:
        result = subprocess.run(
            [sdk, "cat", f"slurm_log/fitpilot-qwen-serve-{job_id}.log"],
            capture_output=True, timeout=20, check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not read the TACC log for job {job_id}. Check tcloud access.") from exc
    log = result.stdout.decode(errors="replace").replace("\x00", "")
    address = re.search(r"^SERVICE_BASE_URL=(\S+)\s*$", log, re.MULTILINE)
    if not address or "Application startup complete" not in log:
        raise RuntimeError(f"Qwen job {job_id} has not reported readiness. Check its TACC log and try again.")
    try:
        url = urlsplit(address[1])
        host, port = url.hostname, url.port
    except ValueError as exc:
        raise RuntimeError("The TACC log contains an invalid service URL.") from exc
    if (url.scheme != "http" or url.path != "/v1" or port != 8000
            or url.query or url.fragment or url.username is not None
            or not host or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", host)):
        raise RuntimeError("Expected an HTTP Qwen endpoint on port 8000 with a /v1 path.")
    return host, port


def start_tunnel(job_id: str, sdk: str, local_port: int) -> subprocess.Popen:
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("Install the OpenSSH client to connect to TACC.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", local_port))
        except OSError as exc:
            raise RuntimeError(f"Local port {local_port} is unavailable. Choose a free --tacc-port.") from exc
    host, port = service_address(job_id, sdk)
    config_path = Path.home() / ".tcloud" / ".userconfig"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        gateways = config["SSHpath"]
        if not isinstance(gateways, list) or len(gateways) != 1:
            raise ValueError
        gateway = gateways[0]
        user = config["UserName"]
        identity = Path(config["AuthFile"]).expanduser()
        gateway_port = int(config["Port"])
        if (not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", gateway)
                or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", user)
                or not identity.is_file() or not 0 < gateway_port <= 65535):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("This launcher needs an existing tcloud account with one SSH gateway and a registered key.") from exc

    return subprocess.Popen([
        ssh, "-N", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "IdentitiesOnly=yes", "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=8",
        "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
        "-i", str(identity), "-p", str(gateway_port),
        "-L", f"127.0.0.1:{local_port}:{host}:{port}", f"{user}@{gateway}",
    ], stdin=subprocess.DEVNULL, start_new_session=True)


def wait_for_model(tunnel: subprocess.Popen, endpoint: str) -> None:
    client = build_opener(ProxyHandler({}))
    for _ in range(20):
        if tunnel.poll() is not None:
            raise RuntimeError("The SSH connection exited. Check the gateway, host key, and local port.")
        try:
            with client.open(f"{endpoint}/models", timeout=2) as response:
                models = json.load(response)["data"]
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(0.25)
            continue
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("The forwarded endpoint did not return a model list.") from exc
        if isinstance(models, list) and any(isinstance(model, dict) and model.get("id") == "qwen3.8-27b" for model in models):
            return
        raise RuntimeError("The forwarded endpoint does not serve qwen3.8-27b.")
    raise RuntimeError("The TACC endpoint did not respond through SSH. Check the service job and gateway forwarding.")

#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${TACC_WORKDIR:?Submit with tcloud submit}"
: "${TACC_USERDIR:?Submit with tcloud submit}"
: "${SLURM_JOB_ID:?Submit with tcloud submit}"
: "${CONDA_PREFIX:?SDK must activate the shared proxy environment}"
test "$CONDA_PREFIX" = /mnt/home/public/course-envs/CSIT6000V/common/proxy || {
    printf 'Unexpected SDK environment: %s\nUse the public Qwen sample setup for this job.\n' "$CONDA_PREFIX" >&2
    exit 1
}
source /mnt/home/public/course-envs/CSIT6000V/project/activate.sh
trap 'if [[ -n "${QWEN_RUN_DIR:-}" ]]; then rm -rf -- "$QWEN_RUN_DIR"; fi' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
export QWEN_CACHE_HOME="$TACC_USERDIR/CSIT6000V-project-cache"
mkdir -p -m 700 "$QWEN_CACHE_HOME"
service_host=$(hostname)
# TACC names IPv4 compute nodes with hyphens. The course runtime may lack DNS for them.
if [[ "$service_host" =~ ^([0-9]{1,3})-([0-9]{1,3})-([0-9]{1,3})-([0-9]{1,3})$ ]]; then
    octets=("${BASH_REMATCH[@]:1}")
    if (( 10#${octets[0]} <= 255 && 10#${octets[1]} <= 255 && 10#${octets[2]} <= 255 && 10#${octets[3]} <= 255 )); then
        printf -v service_host '%d.%d.%d.%d' "$((10#${octets[0]}))" "$((10#${octets[1]}))" \
            "$((10#${octets[2]}))" "$((10#${octets[3]}))"
    fi
fi
printf 'SERVICE_BASE_URL=http://%s:8000/v1\n' "$service_host"
bash "$QWEN_PROJECT_ROOT/serve.sh"

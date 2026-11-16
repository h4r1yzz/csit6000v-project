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
cd "$TACC_WORKDIR"
qwen-python -u run.py

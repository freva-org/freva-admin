#!/usr/bin/env bash

set -euo pipefail

# Default values
USER_ID=0
COMMAND="/usr/local/bin/daily_backup"
DEPLOYMENT_METHOD=""
EMAIL=""
SERVICE=""
BACKUP_DIR=""
SRC_DIR=""
DEBUG=false

print_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --user UID               User ID inside the container (default: 0)
  --service NAME           Name of the container or environment (required)
  --email EMAIL            Email address for cron job output
  --command PATH           Command to run (default: /usr/local/bin/daily_backup)
  --deployment-method TYPE Deployment method: quadlet, conda, or mamba (required)
  --backup-dir DIR         Directory where the backups should be stored.
  --src-dir DIR            Directory where the backups should be stored.
  --debug                  Print cron job content instead of writing it
  --help, -h               Show this help message and exit

Behavior:
  - If deployment method is quadlet: uses 'podman exec --user=UID SERVICE COMMAND'
  - If deployment method is conda or mamba: runs the command directly
  - Adds the command to /etc/cron.daily or the user's crontab
  - Exports current PATH and MAMBA_ROOT_PREFIX to the cron environment
EOF
}

# Parse arguments (supports both --flag=value and --flag value)
while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            USER_ID="$2"; shift 2 ;;
        --user=*)
            USER_ID="${1#*=}"; shift ;;
        --service)
            SERVICE="$2"; shift 2 ;;
        --service=*)
            SERVICE="${1#*=}"; shift ;;
        --email)
            EMAIL="$2"; shift 2 ;;
        --email=*)
            EMAIL="${1#*=}"; shift ;;
        --command)
            COMMAND="$2"; shift 2 ;;
        --command=*)
            COMMAND="${1#*=}"; shift ;;
        --deployment-method)
            DEPLOYMENT_METHOD="$2"; shift 2 ;;
        --deployment-method=*)
            DEPLOYMENT_METHOD="${1#*=}"; shift ;;
        --backup-dir)
            BACKUP_DIR="$2"; shift 2 ;;
        --backup-dir=*)
            BACKUP_DIR="${1#*=}"; shift ;;
        --src-dir)
            SRC_DIR="$2"; shift 2 ;;
        --src-dir=*)
            SRC_DIR="${1#*=}"; shift ;;
        --debug)
            DEBUG=true; shift ;;
        --help|-h)
            print_help; exit 0 ;;
        *)
            echo "Unknown argument: $1"
            echo "Use --help to see usage."
            exit 1 ;;
    esac
done

# Validate required flags
if [[ -z "$SERVICE" ]]; then
    echo "Error: --service is required"
    echo "Use --help to see usage."
    exit 1
fi

if [[ -z "$DEPLOYMENT_METHOD" ]]; then
    echo "Error: --deployment-method is required"
    echo "Use --help to see usage."
    exit 1
fi

# Locate Podman for a Quadlet deployment
locate_podman() {
    if path=$(command -v podman 2>/dev/null); then
        echo "$path"
        return 0
    fi
    echo "Error: Podman is required for a Quadlet deployment" >&2
    exit 1
}

# Build execution command
case "$DEPLOYMENT_METHOD" in
    quadlet)
        RUNTIME_PATH=$(locate_podman)
        EXEC_CMD="$RUNTIME_PATH exec --user=$USER_ID $SERVICE /usr/local/bin/daily-backup -s /data/db -b /backup"
        ;;
    conda|mamba)
        EXEC_CMD="$COMMAND -s $SRC_DIR -b $BACKUP_DIR"
        ;;
    *)
        echo "Error: Unknown or unsupported --deployment-method: $DEPLOYMENT_METHOD"
        echo "Use --help to see usage."
        exit 1
        ;;
esac
EXEC_CMD="$EXEC_CMD 1> /dev/null"
# Get environment variables
ENV_PATH=$(echo "$PATH")
ENV_MAMBA_ROOT="${MAMBA_ROOT_PREFIX:-}"

# Build cron job content
build_cron_script() {
    {
        echo "#!/bin/sh"
        echo "# Run daily backup for $SERVICE"
        [ -n "$EMAIL" ] && echo "MAILTO=$EMAIL"
        echo "export PATH=\"$ENV_PATH\""
        [ -n "$ENV_MAMBA_ROOT" ] && echo "export MAMBA_ROOT_PREFIX=\"$ENV_MAMBA_ROOT\""
        echo "$EXEC_CMD"
    }
}

build_cron_line() {
    [ -n "$EMAIL" ] && echo "MAILTO=$EMAIL"
    echo "PATH=\"$ENV_PATH\""
    [ -n "$ENV_MAMBA_ROOT" ] && echo "MAMBA_ROOT_PREFIX=\"$ENV_MAMBA_ROOT\""
    echo # Command
    echo "0 0 * * * $EXEC_CMD"
}


# If debug is enabled, show the content and exit
if [[ "$DEBUG" == "true" ]]; then
    echo "🧪 Debug Mode: Generated cron job content"
    echo "----------------------------------------"
    if [ -w /etc/cron.daily ]; then
        build_cron_script
    else
        build_cron_line
    fi
    echo "----------------------------------------"
    exit 0
fi

# Normal execution path

# Check if cron job already exists
cron_job_exists() {
    crontab -l 2>/dev/null | grep -F "$EXEC_CMD" >/dev/null
}

# Decide where to place the cron job
if [ -w /etc/cron.daily ]; then
    cron_dir="/etc/cron.daily"
    cron_file="$cron_dir/backup_$SERVICE"
    mkdir -p "$cron_dir"
    build_cron_script > "$cron_file"
    chmod +x "$cron_file"
else
    if command -v crontab >/dev/null; then
        if ! cron_job_exists; then
            TMP_CRON=$(mktemp)
            crontab -l 2>/dev/null > "$TMP_CRON" || true
            build_cron_line >> "$TMP_CRON"
            crontab "$TMP_CRON"
            rm -f "$TMP_CRON"
        fi
    fi
fi

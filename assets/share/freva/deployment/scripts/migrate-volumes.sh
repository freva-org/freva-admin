#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 --service <service> --engine <quadlet|conda> --old-parent-dir <path> --project-name <name>

Options:
  --service          Service name
  --engine           quadlet or conda
  --old-parent-dir   Path to old bind-mounted data
  --project-name     Project name prefix for volumes
EOF
  exit 1
}

# Locate Podman for volume migrations
get_container_cmd() {
  command -v podman 2>/dev/null || true
}

# Setup
BACKUP_DIR="$(mktemp -d /tmp/freva-migration-XXXXXX)"
FAILED_RESTORE=()
MIGRATIONS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service) SERVICE="$2"; shift 2 ;;
    --engine) ENGINE="$2"; shift 2 ;;
    --old-parent-dir) OLD_PARENT_DIR="$2"; shift 2 ;;
    --project-name) PROJECT_NAME="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

[[ -z "${SERVICE:-}" || -z "${ENGINE:-}" || -z "${OLD_PARENT_DIR:-}" || -z "${PROJECT_NAME:-}" ]] && usage
[[ "$ENGINE" != "quadlet" && "$ENGINE" != "conda" ]] && {
  echo "Engine must be 'quadlet' or 'conda'"
  exit 1
}
OCI_PATH=$(get_container_cmd)
if [ "$ENGINE" = "quadlet" ] && [ -z "$OCI_PATH" ]; then
  echo "Podman is required to migrate data into Quadlet volumes"
  exit 1
fi
# Normalize service folder names
normalize_service_name() {
  local path=$1
  local dir
  dir="$(basename "$path")"
  case "$dir" in
    conda|services) echo "conda" ;;
    web_service) echo "freva-web" ;;
    freva_rest|databro*) echo "mongo" ;;
    solr_service) echo "solr" ;;
    vault_service) echo "vault" ;;
    db_service) echo "db" ;;
    *cache*) echo "freva-cacheing";;
    *) echo "$dir" ;;
  esac
}

# Migrate bind-mounted data to volume
migrate_volume() {
  local service="$1"
  local src_path="$2"
  local del_path="$3"
  local vol="${PROJECT_NAME}-${service}_data"
  local volume_backup="${BACKUP_DIR}/${vol}.tar.gz"

  echo ""
  echo "🔧 Migrating $service → $vol"
  echo "   📁 Source path: $src_path"

  MIGRATIONS+=("$service")
  if ! $OCI_PATH volume inspect "$vol" &>/dev/null; then
    echo "   📦 Creating volume: $vol"
    $OCI_PATH volume create "$vol" &>/dev/null
  fi

  echo "   🗃️ Backing up volume to: $volume_backup"
  $OCI_PATH run --rm -v "$vol:/data:ro" -v "$BACKUP_DIR:/backup:Z" alpine \
    tar czf "/backup/$(basename "$volume_backup")" -C /data .

  if ! $OCI_PATH run --rm \
    -v "$vol:/data" \
    -v "$src_path:/backup:ro,Z" \
    alpine sh -c "cp -a /backup/. /data/"; then
    echo "   ❌ Migration failed, restoring to original bind-mount: $src_path"
    rm -rf "$src_path"/*
    if tar -xzf "$volume_backup" -C "$src_path"; then
      echo "   ✅ Restore successful."
    else
      echo "   ❌ Restore failed. Manual fix required: $src_path"
      FAILED_RESTORE+=("$src_path")
    fi
  else
    echo "   ✅ Migration complete. Cleaning up backup."
    rm -f "$volume_backup"
    rm -rf "$del_path"
  fi
}

# Conda-specific legacy migration
migrate_conda_legacy() {
  local service="$1"
  local src_path="$2"
  local del_path="$3"
  local data_path="${OLD_PARENT_DIR}/${PROJECT_NAME}/services/$service"

  MIGRATIONS+=("$service")
  echo ""
  echo "🔧 Migrating $service → conda"
  echo "   📁 Source path: $src_path"
  mkdir -p "${data_path}"
  cp -r "$src_path" "$data_path/data"
  rm -rf "$del_path"
}

# General migration handler (handles both engines)
migrate() {
  local service="$1"
  local data_path
  if [ "$service" != "freva-cacheing" ]; then
    data_path="$OLD_PARENT_DIR/$PROJECT_NAME/services/$service"
  else
    data_path="$OLD_PARENT_DIR/$service"
  fi
  local suffixes

  if [ "$service" = "web" ]; then
    suffixes=(logs django-migration django-static)
  else
    suffixes=(backup logs data)
  fi

  if [ "$ENGINE" != "conda" ]; then
    if [ -d "$data_path/data" ]; then
      migrate_volume "$service" "$data_path/data" "$data_path"
    fi
    rm -rf "$data_path"
  else
    local vol="${PROJECT_NAME}-${service}_data"

    if [ -n "$OCI_PATH" ] && [ ! -d "$data_path/data" ]; then
      mkdir -p "${data_path}"
      local vol_path
      vol_path=$($OCI_PATH volume inspect "$vol" --format='{{.Mountpoint}}' 2>/dev/null || true)

      if [ -n "$vol_path" ] && [ -d "$vol_path" ]; then
        MIGRATIONS+=("$service")
        echo "🔧 Migrating vol: ${service} → conda"
        echo "   📁 Source path: ${vol_path}"
        cp -r "$vol_path" "${data_path}/data"
        echo
      fi

      for suffix in "${suffixes[@]}"; do
        vol="$PROJECT_NAME-${service}_$suffix"
        echo "   📦 Deleting volume: ${vol}"
        $OCI_PATH volume rm -f "$vol" &>/dev/null || true
      done

      rm -f "$OLD_PARENT_DIR/$PROJECT_NAME/compose_services/"*"$service"*.yml 2>/dev/null
    fi
  fi

  # Cleanup orphaned directories
  if [ "$ENGINE" != "conda" ]; then
    if [ ! "$(ls -A "$OLD_PARENT_DIR/$PROJECT_NAME/services" 2>/dev/null)" ]; then
      rm -rf "$OLD_PARENT_DIR/$PROJECT_NAME/"{conda,services}
    fi
  else
    if [ ! "$(ls -A "$OLD_PARENT_DIR/$PROJECT_NAME/compose_services" 2>/dev/null)" ]; then
      rm -rf "$OLD_PARENT_DIR/$PROJECT_NAME/compose_services"
    fi
  fi
}

# Detect legacy bind mounts for services
detect_legacy_services() {
  local base_path="$OLD_PARENT_DIR/$PROJECT_NAME"
  for path in "$base_path"/*; do
    [[ -d "$path" ]] || continue
    local service
    service="$(normalize_service_name "$path")"

    case "$service" in
      freva-web) rm -rf "$path" ;;
      solr) echo -e "$service\t${path}/data\t${path}" ;;
      mongo) echo -e "$service\t${path}/stats\t${path}" ;;
      vault) echo -e "$service\t${path}/files\t${path}" ;;
      db) echo -e "$service\t${path}\t${path}" ;;
      compose*|conda*|freva-cacheing) ;;
    esac
  done
}

# --- Main Migration Logic ---

# Migrate detected legacy services
while IFS=$'\t' read -r service path del_path; do
  if [ "$ENGINE" = "conda" ]; then
    migrate_conda_legacy "$service" "$path" "$del_path"
  else
    migrate_volume "$service" "$path" "$del_path"
  fi
done < <(detect_legacy_services)

# Migrate the explicitly specified service
if ! printf "%s\n" "${MIGRATIONS[@]}" | grep -Fxq "$SERVICE"; then
    migrate "$SERVICE"
fi

# Report failures
if [ "${#FAILED_RESTORE[@]}" -ne 0 ]; then
  echo ""
  echo "❌ Restore failed for the following paths:"
  for path in "${FAILED_RESTORE[@]}"; do
    echo "   - $path"
  done
  exit 1
fi

# Final cleanup
rm -rf "$BACKUP_DIR"
if [ "${#MIGRATIONS[@]}" -ne 0 ]; then
    exit 3
else
    exit 0
fi

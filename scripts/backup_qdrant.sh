#!/bin/bash
# Backup the Qdrant Docker volume (all eternal collections) to a host tarball.
# The volume lives inside Docker's VM — a host-path copy CANNOT reach it;
# this ephemeral container can. Usage: backup_qdrant.sh /path/to/dest-dir
set -euo pipefail
DEST="${1:?usage: backup_qdrant.sh /path/to/dest-dir}"
mkdir -p "$DEST"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="qdrant_data_${STAMP}.tgz"
docker run --rm \
  -v project-godhand-lazarus_qdrant_data:/data:ro \
  -v "$DEST":/backup \
  alpine tar czf "/backup/${OUT}" -C / data
echo "OK: ${DEST}/${OUT} ($(du -h "${DEST}/${OUT}" | cut -f1))"
echo "restore: docker run --rm -v project-godhand-lazarus_qdrant_data:/data -v ${DEST}:/backup alpine sh -c 'cd / && tar xzf /backup/${OUT}'  (container arrêté d'abord)"

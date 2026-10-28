#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
echo "◆ BLACKTHORN INTEL // v0.8.1 // INSTALL"
command -v python3 >/dev/null || { echo "[STOP] Python 3 needed: sudo apt install python3"; exit 1; }
chmod u+x RUN.sh
mkdir -p "$HOME/.local/bin"
if [ -e "$HOME/.local/bin/blackthorn" ] || [ -L "$HOME/.local/bin/blackthorn" ]; then
  echo "[NOTICE] Existing global launcher untouched to avoid changing earlier installations."
  echo "[START] Run from this folder: ./RUN.sh"
else
  ln -s "$(pwd)/RUN.sh" "$HOME/.local/bin/blackthorn"
  echo "[PASS] Current-user launcher created"
fi
echo "[PASS] No root required to run BLACKTHORN"

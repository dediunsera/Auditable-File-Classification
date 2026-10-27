#!/bin/bash
cd "$(dirname "$0")/03_Dataset" || exit 1
PY=""
for c in python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 "$HOME/anaconda3/bin/python3" "$HOME/opt/anaconda3/bin/python3"; do
  if [ -x "$c" ]; then PY="$c"; break; fi
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -z "$PY" ] && { echo "python3 tidak ditemukan di PATH standar."; echo "Tekan Enter untuk menutup."; read; exit 1; }
echo "Menggunakan: $PY"
MAX_PER_ZONE=100 "$PY" build_inventory.py 2>&1 | tee inventory_run.log
echo
echo "=== SELESAI. Jendela ini boleh ditutup. ==="

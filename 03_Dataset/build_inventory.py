#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_inventory.py  — Pengumpul inventaris file untuk dataset SafeClean
Penelitian: SafeClean (macOS safe-cleaning framework) | Ahmad Dedi Jubaedi, M.Kom

Fungsi:
  - Menelusuri direktori sasaran pemeliharaan di Mac ini.
  - Merekam METADATA setiap file (BUKAN isi file): zona, ekstensi, ukuran,
    usia, owner, hidden/symlink.
  - Memberi SARAN label awal (heuristik SafeClean v0): AMAN / BERISIKO / KRITIS.
  - Menulis 3 berkas ke folder 03_Dataset:
        inventory_sample.csv     -> sampel file untuk dilabeli manual
        zone_summary.csv         -> agregat (jumlah file & total byte) per zona
        labeling_worksheet.csv   -> lembar kerja pelabelan (kolom final_label kosong)

Privasi: semua output TETAP di Mac ini. Tidak ada data yang dikirim ke mana pun.

Cara pakai (jalankan di Terminal, dari dalam folder penelitian):
    cd ~/MyDocuments/Penelitian/CleanMyOS/03_Dataset
    python3 build_inventory.py

Opsi:
    MAX_PER_ZONE  -> jumlah maksimum sampel file per zona (default 300)
"""

import os, csv, random, time, pwd, subprocess, sys

random.seed(42)
NOW = time.time()
HOME = os.path.expanduser("~")
MAX_PER_ZONE = int(os.environ.get("MAX_PER_ZONE", "300"))
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

def brew_cache():
    try:
        p = subprocess.run(["brew", "--cache"], capture_output=True, text=True, timeout=10)
        d = p.stdout.strip()
        return d if d and os.path.isdir(d) else None
    except Exception:
        return None

# (zona, root, label_saran_default)
ZONES = [
    # --- cenderung AMAN (reclaimable) ---
    ("cache_user",    os.path.join(HOME, "Library/Caches"),                        "AMAN"),
    ("cache_system",  "/Library/Caches",                                            "AMAN"),
    ("logs_user",     os.path.join(HOME, "Library/Logs"),                           "AMAN"),
    ("trash",         os.path.join(HOME, ".Trash"),                                 "AMAN"),
    ("temp_darwin",   os.environ.get("TMPDIR", "").rstrip("/"),                     "AMAN"),
    ("temp_var",      "/private/var/tmp",                                           "AMAN"),
    ("xcode_dd",      os.path.join(HOME, "Library/Developer/Xcode/DerivedData"),    "AMAN"),
    ("mail_dl",       os.path.join(HOME, "Library/Containers/com.apple.mail/Data/Library/Mail Downloads"), "AMAN"),
    # --- cenderung BERISIKO ---
    ("app_support",   os.path.join(HOME, "Library/Application Support"),            "BERISIKO"),
    ("preferences",   os.path.join(HOME, "Library/Preferences"),                    "BERISIKO"),
    ("containers",    os.path.join(HOME, "Library/Containers"),                     "BERISIKO"),
    # --- cenderung KRITIS ---
    ("keychains",     os.path.join(HOME, "Library/Keychains"),                      "KRITIS"),
    ("launchagents",  os.path.join(HOME, "Library/LaunchAgents"),                   "KRITIS"),
    ("system",        "/System/Library/CoreServices",                              "KRITIS"),
]
# Catatan: zona Downloads/Documents/Desktop (TCC-protected) sengaja dilewati pada
# proses otomatis agar tidak memicu prompt izin macOS. Bisa ditambah pada pass manual.

bc = brew_cache()
if bc:
    ZONES.append(("brew_cache", bc, "AMAN"))

# Aturan proteksi keras (meniru & memperluas isSystemPath aplikasi)
PROTECTED_PREFIXES = ("/System", "/private", "/usr", "/bin", "/sbin", "/etc", "/var")
PROTECTED_SUBSTR = ("/Library/Keychains", "/Library/LaunchDaemons", "/Library/LaunchAgents")
PROTECTED_EXT = {"kext","keychain","cer","cert","pem","p12","provisionprofile","truststore"}
SYSTEM_FILES = {".DS_Store",".localized",".CFUserTextEncoding",".bash_profile",
                ".zshrc",".zprofile",".zshenv",".bashrc"}

def suggest_label(path, ext, default):
    base = os.path.basename(path)
    if any(path.startswith(p) for p in PROTECTED_PREFIXES): return "KRITIS"
    if any(s in path for s in PROTECTED_SUBSTR):            return "KRITIS"
    if ext in PROTECTED_EXT:                                return "KRITIS"
    if base in SYSTEM_FILES:                                return "KRITIS"
    return default

def owner_of(st):
    try: return pwd.getpwuid(st.st_uid).pw_name
    except Exception: return str(st.st_uid)

rows = []            # sampel terlabeli
summary = {}         # zona -> [total_files, total_bytes, sampled]

for zone, root, default in ZONES:
    if not root or not os.path.isdir(root):
        summary[zone] = [0, 0, 0]
        continue
    total_files = 0; total_bytes = 0; reservoir = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None, followlinks=False):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                st = os.lstat(fp)
            except Exception:
                continue
            is_sym = os.path.islink(fp)
            size = st.st_size
            total_files += 1; total_bytes += size
            # reservoir sampling
            if len(reservoir) < MAX_PER_ZONE:
                reservoir.append((fp, st, is_sym))
            else:
                j = random.randint(0, total_files - 1)
                if j < MAX_PER_ZONE:
                    reservoir[j] = (fp, st, is_sym)
    for fp, st, is_sym in reservoir:
        ext = os.path.splitext(fp)[1].lower().lstrip(".")
        age_days = round((NOW - st.st_mtime) / 86400, 1)
        acc_days = round((NOW - st.st_atime) / 86400, 1)
        label = suggest_label(fp, ext, default)
        rows.append({
            "path": fp, "zone": zone, "ext": ext, "size_bytes": st.st_size,
            "age_days": age_days, "last_access_days": acc_days,
            "owner": owner_of(st), "is_hidden": int(os.path.basename(fp).startswith(".")),
            "is_symlink": int(is_sym), "suggested_label": label,
        })
    summary[zone] = [total_files, total_bytes, len(reservoir)]

# ---- tulis output ----
inv = os.path.join(OUT_DIR, "inventory_sample.csv")
with open(inv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
        ["path","zone","ext","size_bytes","age_days","last_access_days","owner","is_hidden","is_symlink","suggested_label"])
    w.writeheader(); w.writerows(rows)

zsum = os.path.join(OUT_DIR, "zone_summary.csv")
with open(zsum, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["zone","total_files","total_bytes","total_mb","sampled"])
    for z,(tf,tb,sm) in summary.items():
        w.writerow([z, tf, tb, round(tb/1048576,1), sm])

wks = os.path.join(OUT_DIR, "labeling_worksheet.csv")
with open(wks, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id","path","zone","ext","size_bytes","age_days","suggested_label","final_label","catatan"])
    for i, r in enumerate(rows, 1):
        w.writerow([i, r["path"], r["zone"], r["ext"], r["size_bytes"], r["age_days"], r["suggested_label"], "", ""])

# ---- ringkasan ke layar ----
print("=" * 60)
print("INVENTARIS SELESAI")
print("=" * 60)
print(f"Total file tersampel : {len(rows)}")
print(f"MAX_PER_ZONE         : {MAX_PER_ZONE}")
from collections import Counter
c = Counter(r["suggested_label"] for r in rows)
print(f"Saran label          : AMAN={c.get('AMAN',0)}  BERISIKO={c.get('BERISIKO',0)}  KRITIS={c.get('KRITIS',0)}")
print()
print(f"{'zona':16} {'file':>8} {'MB':>10} {'sampel':>7}")
for z,(tf,tb,sm) in summary.items():
    print(f"{z:16} {tf:>8} {round(tb/1048576,1):>10} {sm:>7}")
print()
print("Output tersimpan di:", OUT_DIR)
print("  - inventory_sample.csv   (fitur lengkap + saran label)")
print("  - zone_summary.csv       (agregat reclaimable per zona)")
print("  - labeling_worksheet.csv (isi kolom final_label: AMAN/BERISIKO/KRITIS)")

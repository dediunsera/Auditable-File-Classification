# 04_Eksperimen — Evaluasi SafeClean

## Isi
- `run_experiment.py` — pipeline eksperimen (SafeClean L1-L4 + baseline B1/B2/B3, metrik, figur).
- `results_prelim/` — **run PENDAHULUAN** (label sementara = saran heuristik). BUKAN hasil sahih;
  hanya bukti pipeline berjalan. B3_v0 tampak sempurna karena memutar (circular).

## Metode dibandingkan
- **SafeClean** : L1 lokasi + L2 identitas (proteksi keras) + L3 konteks usia + L4 skor risiko berambang.
- **B1_size**  : hapus file terbesar (naif "bebaskan ruang terbanyak").
- **B2_naive** : hapus semua di zona cache/temp/log/trash (tanpa proteksi path/ekstensi).
- **B3_v0**    : hanya aturan isSystemPath awal (ablation SafeClean tanpa L3/L4).

## Metrik
- `CFDR` (utama, target ~0): proporsi file KRITIS yang keliru ditandai boleh-dihapus.
- `unsafe_del_rate`, `precision/recall/F1 (AMAN)`, `specificity_kritis`,
  `reclaimed_gb`, `unsafe_gb`, `reclaimed_ratio`.

## Menjalankan HASIL FINAL (setelah final_label diisi manusia)
```
cd 04_Eksperimen
python3 run_experiment.py \
    --features ../03_Dataset/inventory_sample.csv \
    --labels   ../03_Dataset/labeling_worksheet.xlsx \
    --outdir   results_final
```
Butuh: pandas, matplotlib, openpyxl.
Keluaran: results_metrics.csv, confusion_*.csv, safeclean_threshold_sweep.csv,
fig_cfdr.png, fig_space.png, fig_tradeoff.png.

Validasi fungsi metrik: `python3 run_experiment.py --selftest`

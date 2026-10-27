# Penelitian CleanMyOS — SafeClean

Repositori penelitian untuk paper:
**"SafeClean: A Risk-Aware, Auditable File Classification Framework for Safe Automated macOS Maintenance"**

- Peneliti: Ahmad Dedi Jubaedi, M.Kom
- Target jurnal: IJACSA (SAI) — format dua kolom gaya IEEE, sitasi bernomor [1]
- Aplikasi basis: CleanMyOS Web (PHP + MySQL, 14 modul) di /Applications/XAMPP/xamppfiles/htdocs/cleanmyOS

## Struktur folder
- `01_Proposal/`  — proposal & kerangka manuskrip (mulai: SafeClean_Proposal_v1.docx)
- `02_Literatur/` — paper pembanding & catatan related work
- `03_Dataset/`   — dataset berkas berlabel (aman/berisiko/kritis) + skrip pembangun
- `04_Eksperimen/`— skrip eksperimen, hasil metrik, tabel & gambar

## Status tahapan
1. Sudut riset & kontribusi — SELESAI
2. Pertanyaan penelitian & metode — SELESAI
3. Studi literatur & penguncian novelty — SELESAI
4. Rancang evaluasi & bangun dataset berlabel — SELESAI
5. Jalankan eksperimen & kumpulkan hasil — SELESAI


## Pembeda (novelty)
Framework klasifikasi keamanan file multi-kriteria (lokasi + identitas + konteks dinamis + skor risiko
fail-safe) untuk macOS/APFS, transparan & dapat diaudit, dievaluasi pada dataset berlabel dengan metrik
keselamatan utama: nol penghapusan file kritis (critical false-deletion ≈ 0).

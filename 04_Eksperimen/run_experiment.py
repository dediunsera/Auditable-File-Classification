#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_experiment.py — Eksperimen evaluasi framework SafeClean
Penelitian: SafeClean (safe-cleaning macOS) | Ahmad Dedi Jubaedi, M.Kom

Membandingkan SafeClean (klasifikasi berlapis L1-L4) dengan 3 baseline terhadap
LABEL KEBENARAN manusia, lalu menghitung metrik keselamatan & efektivitas,
menulis tabel hasil dan figur.

Metode yang dibandingkan:
  SafeClean : L1 lokasi + L2 identitas (proteksi keras) + L3 konteks (usia) + L4 skor risiko (ambang)
  B1_size   : hapus file terbesar (naif "bebaskan ruang terbanyak")
  B2_naive  : hapus apa pun di zona bernama cache/temp/log/trash (tanpa proteksi path/ekstensi)
  B3_v0     : hanya aturan isSystemPath awal (= ablation SafeClean tanpa L3/L4)

Metrik:
  CFDR                 : Critical False-Deletion Rate = proporsi file KRITIS yang keliru "boleh dihapus"  (UTAMA, target ~0)
  unsafe_del_rate      : proporsi file (KRITIS atau BERISIKO) yang keliru "boleh dihapus"
  precision/recall/F1  : untuk kelas AMAN (yang diprediksi boleh dihapus)
  specificity_kritis   : kemampuan menahan diri atas file KRITIS
  reclaimed_gb         : ruang file AMAN-benar yang berhasil diidentifikasi (efektivitas)
  unsafe_gb            : ruang file non-AMAN yang keliru ditandai hapus (bahaya)

Cara pakai:
  python3 run_experiment.py --selftest            # validasi fungsi metrik (data sintetis)
  python3 run_experiment.py --features inventory_sample.csv --labels labeling_worksheet.xlsx
  (bila --labels tak diberi / belum dilabeli, dipakai suggested_label => hasil PENDAHULUAN)
"""
import argparse, os, sys, csv
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CLASSES = ["AMAN", "BERISIKO", "KRITIS"]

# ---------- aturan proteksi keras (L1 + L2) ----------
PROTECTED_PREFIXES = ("/System","/private","/usr","/bin","/sbin","/etc","/var")
PROTECTED_SUBSTR   = ("/Library/Keychains","/Library/LaunchDaemons","/Library/LaunchAgents")
PROTECTED_EXT      = {"kext","keychain","cer","cert","pem","p12","provisionprofile","truststore"}
SYSTEM_FILES       = {".DS_Store",".localized",".CFUserTextEncoding",".bash_profile",
                      ".zshrc",".zprofile",".zshenv",".bashrc"}

def is_hard_protected(path, ext):
    base = os.path.basename(str(path))
    if any(str(path).startswith(p) for p in PROTECTED_PREFIXES): return True
    if any(s in str(path) for s in PROTECTED_SUBSTR):            return True
    if str(ext).lower() in PROTECTED_EXT:                        return True
    if base in SYSTEM_FILES:                                     return True
    return False

# prior risiko per zona (pengetahuan domain macOS)
ZONE_RISK = {
    "cache_user":0.05,"cache_system":0.05,"logs_user":0.10,"trash":0.02,
    "temp_darwin":0.05,"temp_var":0.05,"xcode_dd":0.05,"mail_dl":0.10,"brew_cache":0.05,
    "app_support":0.55,"preferences":0.60,"containers":0.55,"downloads":0.45,
    "keychains":0.98,"launchagents":0.95,"system":0.98,"documents":0.9,"desktop":0.9,
}

# ---------- SafeClean: L1-L4 ----------
def safeclean_risk(row):
    """Kembalikan skor risiko 0..1 (L1/L2 override -> 1.0)."""
    if is_hard_protected(row["path"], row.get("ext","")):
        return 1.0
    base = ZONE_RISK.get(row["zone"], 0.5)                 # L1 (prior zona) = sinyal dominan
    age = float(row.get("age_days", 0) or 0)
    recency_risk = max(0.0, 1.0 - age/30.0)                # L3: modifier kecil (in-use diperiksa saat deploy)
    return min(1.0, base + 0.10*recency_risk)              # L4: agregasi (lokasi dominan)

def predict_safeclean(df, t_low=0.30, t_high=0.70):
    out=[]
    for _,r in df.iterrows():
        s = safeclean_risk(r)
        out.append("KRITIS" if s>=t_high else ("BERISIKO" if s>=t_low else "AMAN"))
    return out

# ---------- Baselines ----------
def predict_b1_size(df, top_frac=0.30):
    # hapus (AMAN) file terbesar sampai top_frac dari total byte; sisanya "keep"(BERISIKO)
    d = df.copy(); d["_b"]=d["size_bytes"].astype(float)
    d = d.sort_values("_b", ascending=False)
    total = d["_b"].sum(); acc=0.0; delete=set()
    for idx,b in zip(d.index, d["_b"]):
        if acc < top_frac*total:
            delete.add(idx); acc+=b
    return ["AMAN" if i in delete else "BERISIKO" for i in df.index]

CACHE_ZONES = {"cache_user","cache_system","logs_user","trash","temp_darwin","temp_var","xcode_dd","mail_dl","brew_cache"}
def predict_b2_naive(df):
    return ["AMAN" if r["zone"] in CACHE_ZONES else "BERISIKO" for _,r in df.iterrows()]

def predict_b3_v0(df):
    # isSystemPath awal: KRITIS bila hard-protected, selain itu pakai label_default zona (suggested)
    return list(df["suggested_label"])

# ---------- Metrik ----------
def metrics(y_true, y_pred, sizes):
    import numpy as np
    yt=list(y_true); yp=list(y_pred); sz=[float(x) for x in sizes]
    n=len(yt)
    pred_del = [p=="AMAN" for p in yp]
    true_aman=[t=="AMAN" for t in yt]
    true_kritis=[t=="KRITIS" for t in yt]
    true_unsafe=[t in("KRITIS","BERISIKO") for t in yt]
    TP=sum(1 for i in range(n) if pred_del[i] and true_aman[i])
    FP=sum(1 for i in range(n) if pred_del[i] and not true_aman[i])
    FN=sum(1 for i in range(n) if (not pred_del[i]) and true_aman[i])
    prec=TP/(TP+FP) if TP+FP else 0.0
    rec =TP/(TP+FN) if TP+FN else 0.0
    f1  =2*prec*rec/(prec+rec) if prec+rec else 0.0
    nk=sum(true_kritis); nu=sum(true_unsafe)
    cfdr=sum(1 for i in range(n) if pred_del[i] and true_kritis[i])/nk if nk else 0.0
    unsafe_rate=sum(1 for i in range(n) if pred_del[i] and true_unsafe[i])/nu if nu else 0.0
    spec_k = sum(1 for i in range(n) if (not pred_del[i]) and true_kritis[i])/nk if nk else 0.0
    GB=1073741824.0
    reclaimed=sum(sz[i] for i in range(n) if pred_del[i] and true_aman[i])/GB
    unsafe_gb=sum(sz[i] for i in range(n) if pred_del[i] and not true_aman[i])/GB
    total_aman_gb=sum(sz[i] for i in range(n) if true_aman[i])/GB
    reclaimed_ratio=reclaimed/total_aman_gb if total_aman_gb else 0.0
    return dict(precision_aman=round(prec,4), recall_aman=round(rec,4), f1_aman=round(f1,4),
                CFDR=round(cfdr,4), unsafe_del_rate=round(unsafe_rate,4),
                specificity_kritis=round(spec_k,4),
                reclaimed_gb=round(reclaimed,3), unsafe_gb=round(unsafe_gb,3),
                reclaimed_ratio=round(reclaimed_ratio,4))

def confusion(y_true,y_pred):
    m={a:{b:0 for b in CLASSES} for a in CLASSES}
    for t,p in zip(y_true,y_pred):
        if t in m and p in m[t]: m[t][p]+=1
    return m

# ---------- Self test ----------
def selftest():
    # 4 file: 2 AMAN, 1 BERISIKO, 1 KRITIS; prediksi sengaja 1 salah-kritis
    yt=["AMAN","AMAN","BERISIKO","KRITIS"]
    yp=["AMAN","BERISIKO","AMAN","AMAN"]   # file KRITIS keliru dihapus -> CFDR harus 1.0
    sz=[100,100,100,100]
    r=metrics(yt,yp,sz)
    assert r["CFDR"]==1.0, r
    assert r["recall_aman"]==0.5, r      # 1 dari 2 AMAN tertangkap
    # TP=1(AMAN benar), FP=2(BERISIKO&KRITIS dihapus) -> precision=1/3
    assert abs(r["precision_aman"]-0.3333)<0.01, r
    print("SELF-TEST OK:", r)

# ---------- Main ----------
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--features",default="inventory_sample.csv")
    ap.add_argument("--labels",default=None)
    ap.add_argument("--outdir",default=".")
    a=ap.parse_args()
    if a.selftest:
        selftest(); return

    df=pd.read_csv(a.features)
    provisional=True
    if a.labels and os.path.exists(a.labels):
        lab=pd.read_excel(a.labels, sheet_name="Pelabelan")
        lab=lab[["path","final_label"]].dropna()
        df=df.merge(lab, on="path", how="left")
        # pakai final_label bila ada; sisanya fallback suggested
        df["label"]=df["final_label"].fillna(df["suggested_label"])
        provisional = df["final_label"].isna().any() or (df["final_label"]==df["suggested_label"]).all()
    else:
        df["label"]=df["suggested_label"]
    y_true=list(df["label"])

    methods={
        "SafeClean":predict_safeclean(df),
        "B1_size":predict_b1_size(df),
        "B2_naive":predict_b2_naive(df),
        "B3_v0":predict_b3_v0(df),
    }
    os.makedirs(a.outdir,exist_ok=True)
    rows=[]
    for name,yp in methods.items():
        m=metrics(y_true,yp,df["size_bytes"]); m={"method":name,**m}; rows.append(m)
        cm=confusion(y_true,yp)
        with open(os.path.join(a.outdir,f"confusion_{name}.csv"),"w",newline="") as f:
            w=csv.writer(f); w.writerow(["true\\pred"]+CLASSES)
            for t in CLASSES: w.writerow([t]+[cm[t][p] for p in CLASSES])
    res=pd.DataFrame(rows)
    res.to_csv(os.path.join(a.outdir,"results_metrics.csv"),index=False)

    # threshold sweep SafeClean (RQ3)
    sweep=[]
    for t in [x/100 for x in range(5,100,5)]:
        yp=predict_safeclean(df,t_low=t,t_high=0.95)
        m=metrics(y_true,yp,df["size_bytes"])
        sweep.append({"t_high":t,"CFDR":m["CFDR"],"reclaimed_ratio":m["reclaimed_ratio"],"f1_aman":m["f1_aman"]})
    sw=pd.DataFrame(sweep); sw.to_csv(os.path.join(a.outdir,"safeclean_threshold_sweep.csv"),index=False)

    # ---------- gaya figur publikasi ----------
    BLUE, ORANGE, GRID, INK, MUTE = "#1C7ED6", "#E8590C", "#E6E6E6", "#1A1A1A", "#6B7280"
    plt.rcParams.update({
        "font.family":"DejaVu Sans","font.size":10,"axes.titlesize":12,
        "axes.titleweight":"bold","axes.labelsize":10,"axes.edgecolor":MUTE,
        "axes.linewidth":0.8,"axes.titlepad":12,"xtick.color":INK,"ytick.color":INK,
        "text.color":INK,"axes.labelcolor":INK,"figure.dpi":200,"savefig.dpi":200,
        "savefig.bbox":"tight","savefig.facecolor":"white","figure.facecolor":"white",
    })
    def _clean(ax, ygrid=True):
        for s in ("top","right"): ax.spines[s].set_visible(False)
        for s in ("left","bottom"): ax.spines[s].set_color(MUTE)
        if ygrid:
            ax.yaxis.grid(True, color=GRID, linewidth=0.9, zorder=0); ax.set_axisbelow(True)
        ax.tick_params(length=0)
    SAFE = {"SafeClean","B3_v0"}
    labels = list(res["method"])
    cols = [BLUE if m in SAFE else ORANGE for m in labels]

    # ---- figur 1: CFDR per metode ----
    fig, ax = plt.subplots(figsize=(6.4,4.0))
    vals = list(res["CFDR"]*100)
    bars = ax.bar(labels, vals, color=cols, width=0.62, zorder=3)
    for b,v in zip(bars,vals):
        ax.text(b.get_x()+b.get_width()/2, v+max(vals)*0.02+0.3, f"{v:.1f}%",
                ha="center", va="bottom", fontsize=9.5, fontweight="bold",
                color=(BLUE if b.get_facecolor()[0]<0.3 else ORANGE))
    ax.set_ylabel("Critical False-Deletion Rate (%)")
    ax.set_title("Safety: critical files erroneously marked deletable")
    ax.set_ylim(0, max(vals)*1.18 if max(vals)>0 else 1)
    _clean(ax)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=BLUE,label="Safe method (lower is better)"),
                       Patch(facecolor=ORANGE,label="Unsafe method")],
              frameon=False, loc="upper left", fontsize=9)
    ax.annotate("Target ≈ 0%", xy=(0,0.2), xytext=(0.0,max(vals)*0.33 if max(vals)>0 else 0.3),
                fontsize=8.5, color=MUTE)
    fig.tight_layout(); fig.savefig(os.path.join(a.outdir,"fig_cfdr.png")); plt.close(fig)

    # ---- figur 2: reclaimed vs unsafe GB (grouped) ----
    import numpy as np
    fig, ax = plt.subplots(figsize=(6.8,4.0))
    x=np.arange(len(labels)); w=0.38
    r=list(res["reclaimed_gb"]); u=list(res["unsafe_gb"])
    b1=ax.bar(x-w/2, r, w, label="Reclaimed safe space", color=BLUE, zorder=3)
    b2=ax.bar(x+w/2, u, w, label="Unsafe space deleted", color=ORANGE, zorder=3)
    for bars in (b1,b2):
        for b in bars:
            h=b.get_height()
            if h>0: ax.text(b.get_x()+b.get_width()/2, h+max(r+u+[0.01])*0.02,
                            f"{h:.2f}", ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("Space (GB)")
    ax.set_title("Effectiveness vs. risk: space freed per method")
    ax.set_ylim(0, max(r+u+[0.01])*1.22)
    ax.legend(frameon=False, fontsize=9, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5,1.0))
    _clean(ax)
    fig.tight_layout(); fig.savefig(os.path.join(a.outdir,"fig_space.png")); plt.close(fig)

    # ---- figur 3: sensitivitas ambang (efektivitas & keamanan vs ambang) ----
    fig, ax = plt.subplots(figsize=(6.4,4.0))
    xt=list(sw["t_high"]); yy=list(sw["reclaimed_ratio"]*100); cf=list(sw["CFDR"]*100)
    ax.plot(xt, yy, "-", color=BLUE, linewidth=2, zorder=2, label="Ruang aman tereklamasi (%)")
    mc=[ORANGE if c>0 else BLUE for c in cf]
    ax.scatter(xt, yy, s=46, color=mc, edgecolor="white", linewidth=1.2, zorder=3)
    ax.set_xlabel("Risk threshold t_high  (looser toward the right)")
    ax.set_ylabel("Reclaimed safe space (%)")
    ax.set_title("Threshold sensitivity: effectiveness vs. safety")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0],[0],color=BLUE,lw=2,marker="o",label="Safe point (CFDR=0)"),
                       Line2D([0],[0],color="white",marker="o",markerfacecolor=ORANGE,
                              markeredgecolor="white",lw=0,label="Risky point (CFDR>0)")],
              frameon=False, fontsize=9, loc="upper left")
    _clean(ax)
    fig.tight_layout(); fig.savefig(os.path.join(a.outdir,"fig_tradeoff.png")); plt.close(fig)

    # ----- Train/test split: select threshold on TRAIN, evaluate on TEST (avoid tuning-on-test) -----
    import numpy as np
    tr = df.groupby("label", group_keys=False).sample(frac=0.6, random_state=42)
    te = df.drop(tr.index)
    best_t, best_r = 0.30, -1.0
    for t in [x/100 for x in range(5,96,5)]:
        m=metrics(tr["label"],predict_safeclean(tr,t_low=t,t_high=0.95),tr["size_bytes"])
        if m["CFDR"]==0.0 and m["unsafe_del_rate"]==0.0 and m["reclaimed_ratio"]>best_r:
            best_r=m["reclaimed_ratio"]; best_t=t
    te_methods={
        "SafeClean":predict_safeclean(te,t_low=best_t,t_high=0.95),
        "B1_size":predict_b1_size(te),
        "B2_naive":predict_b2_naive(te),
        "B3_v0":list(te["suggested_label"]),
    }
    srows=[]
    for name,yp in te_methods.items():
        srows.append({"method":name,**metrics(te["label"],yp,te["size_bytes"])})
    sres=pd.DataFrame(srows); sres.to_csv(os.path.join(a.outdir,"test_metrics.csv"),index=False)
    with open(os.path.join(a.outdir,"split_info.txt"),"w") as f:
        f.write(f"train={len(tr)} test={len(te)} selected_t_low={best_t} "
                f"(max reclaimed s.t. CFDR=0 and unsafe=0 on train)\n")
    cm_sc=confusion(list(te["label"]), te_methods["SafeClean"])
    te2=te.reset_index(drop=True); ypsc=te_methods["SafeClean"]; ea=[]
    for i in range(len(te2)):
        if te2.loc[i,"label"]!=ypsc[i]:
            ea.append({"true":te2.loc[i,"label"],"pred":ypsc[i],"zone":te2.loc[i,"zone"]})
    ea=pd.DataFrame(ea)
    ea_sum=(ea.groupby(["true","pred","zone"]).size().reset_index(name="count").sort_values("count",ascending=False)
            if len(ea) else pd.DataFrame(columns=["true","pred","zone","count"]))
    ea_sum.to_csv(os.path.join(a.outdir,"error_analysis.csv"),index=False)
    cmat=np.array([[cm_sc[t][p] for p in CLASSES] for t in CLASSES])
    figc,axc=plt.subplots(figsize=(4.4,3.8))
    im=axc.imshow(cmat,cmap="Blues")
    axc.set_xticks(range(3)); axc.set_yticks(range(3))
    axc.set_xticklabels(["safe","risky","critical"]); axc.set_yticklabels(["safe","risky","critical"])
    axc.set_xlabel("Predicted label"); axc.set_ylabel("True label")
    axc.set_title("SafeClean confusion matrix (test set)")
    for i in range(3):
        for j in range(3):
            axc.text(j,i,int(cmat[i][j]),ha="center",va="center",fontsize=11,
                     color="white" if cmat[i][j]>cmat.max()/2 else "#10395E",fontweight="bold")
    figc.tight_layout(); figc.savefig(os.path.join(a.outdir,"fig_confusion.png"),dpi=200); plt.close(figc)
    print("\nTEST-SET (threshold selected on train, t_low=%.2f, train=%d test=%d):"%(best_t,len(tr),len(te)))
    print(sres.to_string(index=False))
    print("\nError analysis (top misclassifications on test):")
    print(ea_sum.head(10).to_string(index=False))

    tag="PENDAHULUAN (label=saran, belum divalidasi manusia)" if provisional else "FINAL (label manusia)"
    print("="*64); print("HASIL EKSPERIMEN —", tag); print("="*64)
    print(res.to_string(index=False))
    print("\nOutput:", os.path.abspath(a.outdir))
    print("  results_metrics.csv, confusion_*.csv, safeclean_threshold_sweep.csv")
    print("  fig_cfdr.png, fig_space.png, fig_tradeoff.png")
    if provisional:
        print("\n[!] CATATAN: ini hasil PENDAHULUAN. B3_v0 akan tampak sempurna karena label "
              "sementara = keluaran heuristiknya sendiri. Angka sahih muncul setelah final_label diisi manusia.")

if __name__=="__main__":
    main()

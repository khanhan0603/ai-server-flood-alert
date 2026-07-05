"""
analyze_benchmark.py
Đánh giá model dự báo lũ bằng các metric khoa học:
  - TSS (True Skill Statistic) — Allouche et al. 2006
  - CSI (Critical Success Index / IoU) — chuẩn flood susceptibility modeling
  - F1-score
  - Sensitivity (Recall), Specificity

Định nghĩa nhãn:
  event thật  → label = 1 (flood)
  control sau → label = 0 (non-flood) — sạch nhất, 10+ ngày sau lũ

Chạy: python analyze_benchmark.py --folder benchmark_results
"""

import os
import json
import argparse
import pandas as pd

# ── Cấu hình ────────────────────────────────────────────────────────────────
ALERT_LABELS = {"HIGH", "MEDIUM"}
HIGH_LABELS  = {"HIGH"}
EVENTS = [f"E{str(i).zfill(3)}" for i in range(1, 9)]  # bỏ E009 

EVENT_NAMES = {
    "E001": "Bão Wutip",
    "E002": "Bão Wipha",
    "E003": "Bão Kajiki",
    "E004": "Bão Bualoi",
    "E005": "Bão Matmo",
    "E006": "Bão FengShen",
    "E007": "Mưa lớn Miền Trung",
    "E008": "Lũ sông Mã",
    "E009": "Lũ quét Điện Biên",
}

FILE_TYPES = {
    "event":       "Sự kiện thật",
    "neg_before":  "Control trước",
    "neg_after":   "Control sau",
    "neg_spatial": "Control vùng khác",
}

BUCKETS = ["overall", "day_1", "day_2", "day_3"]

BUCKET_LABELS = {
    "overall": "TỔNG HỢP (Overall Risk)",
    "day_1":   "DỰ BÁO TRƯỚC 1 NGÀY",
    "day_2":   "DỰ BÁO TRƯỚC 2 NGÀY",
    "day_3":   "DỰ BÁO TRƯỚC 3 NGÀY",
}


# ── Đọc file JSON ────────────────────────────────────────────────────────────
def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Parse 1 file → stats theo overall + day_1/2/3 ───────────────────────────
def parse_file(data: dict) -> dict:
    buckets = {b: [] for b in BUCKETS}

    for item in data.get("results", []):
        points = item.get("summary", {}).get("results", [])
        for point in points:
            pred = point.get("prediction")
            if not pred:
                continue

            if pred.get("overall_risk"):
                buckets["overall"].append({
                    "risk_level":        pred["overall_risk"],
                    "flood_probability": pred.get("probability", 0),
                })

            forecast = pred.get("forecast", {})
            for day in ["day_1", "day_2", "day_3"]:
                dp = forecast.get(day, {})
                if dp.get("risk_level"):
                    buckets[day].append({
                        "risk_level":        dp["risk_level"],
                        "flood_probability": dp.get("probability", 0),
                    })

    def calc(lst):
        total = len(lst)
        if total == 0:
            return {
                "total": 0, "high": 0, "alert": 0,
                "high_pct": 0.0, "alert_pct": 0.0, "avg_prob": 0.0,
            }
        high  = sum(1 for p in lst if p["risk_level"] in HIGH_LABELS)
        alert = sum(1 for p in lst if p["risk_level"] in ALERT_LABELS)
        avg_p = sum(p["flood_probability"] for p in lst) / total
        return {
            "total":     total,
            "high":      high,
            "alert":     alert,
            "high_pct":  round(high  / total * 100, 1),
            "alert_pct": round(alert / total * 100, 1),
            "avg_prob":  round(avg_p  * 100, 1),
        }

    return {k: calc(v) for k, v in buckets.items()}


# ── Tính TSS, CSI, F1 từ event vs control_after ─────────────────────────────
def calc_scientific_metrics(ev: dict, ctrl_after: dict) -> dict:
    """
    ev          : stats của event thật   (label = 1)
    ctrl_after  : stats của control sau  (label = 0)

    TP = event bị cảnh báo MEDIUM+      (cảnh báo đúng khi có lũ)
    FN = event không bị cảnh báo        (bỏ sót khi có lũ)
    FP = control sau bị cảnh báo MEDIUM+(cảnh báo sai khi không có lũ)
    TN = control sau không bị cảnh báo  (đúng khi không có lũ)
    """
    if ev["total"] == 0 or ctrl_after["total"] == 0:
        return {"TSS": None, "CSI": None, "F1": None,
                "Sensitivity": None, "Specificity": None,
                "TP": 0, "FN": 0, "FP": 0, "TN": 0}

    TP = ev["alert"]
    FN = ev["total"] - ev["alert"]
    FP = ctrl_after["alert"]
    TN = ctrl_after["total"] - ctrl_after["alert"]

    sensitivity = TP / (TP + FN) if (TP + FN) > 0 else 0  # Recall
    specificity = TN / (TN + FP) if (TN + FP) > 0 else 0
    tss         = round(sensitivity + specificity - 1, 3)
    csi         = round(TP / (TP + FP + FN), 3) if (TP + FP + FN) > 0 else 0
    f1          = round(2*TP / (2*TP + FP + FN), 3) if (2*TP + FP + FN) > 0 else 0

    return {
        "TP": TP, "FN": FN, "FP": FP, "TN": TN,
        "Sensitivity": round(sensitivity, 3),
        "Specificity":  round(specificity, 3),
        "TSS":          tss,
        "CSI":          csi,
        "F1":           f1,
    }


def tss_verdict(tss, bucket):
    """Ngưỡng TSS theo Allouche et al. 2006 và thực tiễn flood modeling."""
    if tss is None:
        return "N/A"
    if bucket == "day_1":
        if tss >= 0.5:   return "✅ TỐT (TSS ≥ 0.5)"
        elif tss >= 0.2: return "⚠️  KHÁ (TSS 0.2–0.5)"
        elif tss >= 0:   return "⚠️  YẾU (TSS 0–0.2)"
        else:            return "❌ CHƯA ĐẠT (TSS < 0)"
    elif bucket == "day_2":
        if tss >= 0.3:   return "✅ TỐT (TSS ≥ 0.3)"
        elif tss >= 0.1: return "⚠️  KHÁ (TSS 0.1–0.3)"
        elif tss >= 0:   return "⚠️  Suy giảm bình thường"
        else:            return "⚠️  Khó phân biệt 2 ngày — xem Limitations"
    elif bucket == "day_3":
        if tss >= 0.1:   return "✅ Còn tín hiệu (TSS ≥ 0.1)"
        elif tss >= 0:   return "⚠️  Suy giảm rõ ở 3 ngày — đặc tính tự nhiên"
        else:            return "⚠️  3 ngày khó dự báo — ghi Limitations"
    else:  # overall
        if tss >= 0.4:   return "✅ TỐT (TSS ≥ 0.4)"
        elif tss >= 0.2: return "⚠️  KHÁ (TSS 0.2–0.4)"
        elif tss >= 0:   return "⚠️  YẾU"
        else:            return "❌ CHƯA ĐẠT"


# ── Đọc tất cả file → DataFrame ─────────────────────────────────────────────
def analyze(folder: str) -> pd.DataFrame:
    rows = []
    for eid in EVENTS:
        for ftype in FILE_TYPES:
            suffix = "" if ftype == "event" else f"_{ftype}"
            path   = os.path.join(folder, f"{eid}{suffix}.json")
            data   = load_json(path)
            if data is None:
                continue
            stats = parse_file(data)
            for bucket, s in stats.items():
                rows.append({
                    "event":      eid,
                    "event_name": EVENT_NAMES.get(eid, eid),
                    "type":       ftype,
                    "type_label": FILE_TYPES[ftype],
                    "bucket":     bucket,
                    **s,
                })
    return pd.DataFrame(rows)


# ── In báo cáo ───────────────────────────────────────────────────────────────
def print_report(df: pd.DataFrame):
    W = 74

    for bucket in BUCKETS:
        bdf = df[df["bucket"] == bucket]
        print(f"\n{'='*W}")
        print(f"  {BUCKET_LABELS[bucket]}")
        print(f"{'='*W}")

        # ── Chi tiết từng event ──────────────────────────────────────
        for eid in EVENTS:
            sub = bdf[bdf["event"] == eid]
            if sub.empty:
                continue

            ev_row  = sub[sub["type"] == "event"]
            aft_row = sub[sub["type"] == "neg_after"]
            if ev_row.empty or aft_row.empty:
                continue

            ev_stats  = ev_row.iloc[0].to_dict()
            aft_stats = aft_row.iloc[0].to_dict()
            m = calc_scientific_metrics(ev_stats, aft_stats)

            print(f"\n  {eid} {EVENT_NAMES.get(eid, eid)}")
            print(f"  {'─'*64}")
            print(f"  {'Loại':<22} {'Điểm':>6}  {'HIGH':>10}  {'MEDIUM+':>10}  {'Prob TB':>8}")
            print(f"  {'─'*64}")

            for ftype, flabel in FILE_TYPES.items():
                row = sub[sub["type"] == ftype]
                if row.empty:
                    continue
                r = row.iloc[0]
                print(
                    f"  {flabel:<22} {int(r['total']):>6}  "
                    f"{int(r['high']):>4} ({r['high_pct']:>5.1f}%)  "
                    f"{int(r['alert']):>4} ({r['alert_pct']:>5.1f}%)  "
                    f"{r['avg_prob']:>7.1f}%"
                )

            # In confusion matrix mini + metrics
            print(f"  {'─'*64}")
            print(f"  Confusion (event vs control sau):  "
                  f"TP={m['TP']}  FN={m['FN']}  FP={m['FP']}  TN={m['TN']}")
            if m["TSS"] is not None:
                print(f"  Sensitivity={m['Sensitivity']:.3f}  "
                      f"Specificity={m['Specificity']:.3f}  "
                      f"TSS={m['TSS']:.3f}  CSI={m['CSI']:.3f}  F1={m['F1']:.3f}")

        # ── Tổng kết toàn bộ 9 event ─────────────────────────────────
        print(f"\n  {'─'*64}")
        print(f"  TỔNG 9 SỰ KIỆN — METRIC KHOA HỌC (event vs control sau)")
        print(f"  {'─'*64}")
        print(f"  {'Loại':<22} {'Điểm':>6}  {'HIGH':>10}  {'MEDIUM+':>10}  {'Prob TB':>8}")
        print(f"  {'─'*64}")

        summary_stats = {}
        for ftype, flabel in FILE_TYPES.items():
            sub   = bdf[bdf["type"] == ftype]
            if sub.empty:
                continue
            total    = int(sub["total"].sum())
            high     = int(sub["high"].sum())
            alert    = int(sub["alert"].sum())
            avg_prob = round(sub["avg_prob"].mean(), 1)
            hp = round(high  / total * 100, 1) if total else 0
            ap = round(alert / total * 100, 1) if total else 0
            summary_stats[ftype] = {
                "total": total, "high": high, "alert": alert,
                "high_pct": hp, "alert_pct": ap, "avg_prob": avg_prob,
            }
            print(
                f"  {flabel:<22} {total:>6}  "
                f"{high:>4} ({hp:>5.1f}%)  "
                f"{alert:>4} ({ap:>5.1f}%)  "
                f"{avg_prob:>7.1f}%"
            )

        # Tính metric tổng hợp
        if "event" in summary_stats and "neg_after" in summary_stats:
            m_total = calc_scientific_metrics(
                summary_stats["event"],
                summary_stats["neg_after"],
            )
            print(f"\n  {'─'*64}")
            print(f"  METRIC KHOA HỌC TỔNG HỢP (Allouche et al. 2006)")
            print(f"  {'─'*64}")
            print(f"  TP={m_total['TP']:>6}  FN={m_total['FN']:>6}  "
                  f"FP={m_total['FP']:>6}  TN={m_total['TN']:>6}")
            print(f"  Sensitivity (Recall) = {m_total['Sensitivity']:.3f}")
            print(f"  Specificity          = {m_total['Specificity']:.3f}")
            print(f"  TSS                  = {m_total['TSS']:.3f}   "
                  f"(tốt ≥ 0.5, chấp nhận 0.2–0.5, kém < 0.2)")
            print(f"  CSI (IoU)            = {m_total['CSI']:.3f}   "
                  f"(tốt ≥ 0.5, chấp nhận 0.3–0.5, kém < 0.3)")
            print(f"  F1-score             = {m_total['F1']:.3f}")
            print(f"\n  Kết luận: {tss_verdict(m_total['TSS'], bucket)}")

    print(f"\n{'='*W}")
    print("  GHI CHÚ PHƯƠNG PHÁP")
    print(f"{'='*W}")
    print("  - TSS: True Skill Statistic (Allouche et al. 2006)")
    print("    Không bị ảnh hưởng bởi mất cân bằng dữ liệu")
    print("    TSS = Sensitivity + Specificity - 1")
    print("  - CSI: Critical Success Index (Lee et al. 2017)")
    print("    CSI = TP / (TP + FP + FN)")
    print("  - Control sau (neg_after) dùng làm nhãn 0 vì cách event")
    print("    tối thiểu 10 ngày, hoàn lưu bão đã tan hoàn toàn")
    print("  - Control trước (neg_before) KHÔNG dùng làm nhãn 0 vì")
    print("    điều kiện tiền bão tích lũy làm bias kết quả")
    print(f"{'='*W}\n")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", "-f", default="benchmark_results")
    parser.add_argument("--csv",    "-o", default=None)
    args = parser.parse_args()

    df = analyze(args.folder)

    if df.empty:
        print("Không tìm thấy file JSON nào trong:", args.folder)
        return

    print_report(df)

    if args.csv:
        df.to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"Đã lưu CSV: {args.csv}")


if __name__ == "__main__":
    main()
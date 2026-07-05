"""
analyze_benchmark.py
Đánh giá model dự báo lũ — đơn vị tỉnh-ngày (province-day)

Lý do dùng province-day thay vì point-level:
  Ground truth (White Book) chỉ ghi nhận ở cấp tỉnh, không có tọa độ cụ thể.
  Gán nhãn flood cho từng điểm lưới trong tỉnh là quá thô — phạt oan model
  ở các vùng núi/cao nguyên không thực sự ngập trong cùng tỉnh.
  → Chuyển sang province-day: 1 tỉnh trong 1 ngày = có lũ nếu ≥ 30% điểm báo MEDIUM+

Metric khoa học:
  - TSS (True Skill Statistic) — Allouche et al. 2006
  - CSI (Critical Success Index) — Lee et al. 2017
  - F1-score, Sensitivity, Specificity

Nhãn:
  event thật  → label = 1 (flood)
  control sau → label = 0 (non-flood) — cách event 10+ ngày, hoàn lưu đã tan

Chạy: python analyze_benchmark.py --folder benchmark_results
"""

import os
import json
import argparse
import pandas as pd

# ── Cấu hình ────────────────────────────────────────────────────────────────
ALERT_LABELS = {"HIGH", "MEDIUM"}
HIGH_LABELS  = {"HIGH"}

# Ngưỡng: tỉnh-ngày = có lũ nếu ≥ 30% điểm báo MEDIUM+
# Khớp với đặc tính recall-first của model (threshold=0.35)
PROVINCE_ALERT_THRESHOLD = 0.30

EVENTS = [f"E{str(i).zfill(3)}" for i in range(1, 9)]  # E001–E008, bỏ E009 (lũ quét)

EVENT_NAMES = {
    "E001": "Bão Wutip",
    "E002": "Bão Wipha",
    "E003": "Bão Kajiki",
    "E004": "Bão Bualoi",
    "E005": "Bão Matmo",
    "E006": "Bão FengShen",
    "E007": "Mưa lớn Miền Trung",
    "E008": "Lũ sông Mã",
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


# ── Parse 1 file → danh sách province-day ───────────────────────────────────
def parse_province_days(data: dict) -> list:
    """
    Trả về list các dict:
    {
        "date": "2025-06-10",
        "province": "hue",
        "overall":  True/False,  # tỉnh-ngày có lũ theo overall_risk
        "day_1":    True/False,
        "day_2":    True/False,
        "day_3":    True/False,
        "avg_prob": float,
    }
    Mỗi phần tử = 1 tỉnh × 1 ngày
    """
    # Gom theo (date, province)
    groups = {}

    for item in data.get("results", []):
        date     = item.get("date", "")
        province = item.get("province", "")
        key      = (date, province)

        if key not in groups:
            groups[key] = {b: [] for b in BUCKETS}
            groups[key]["probs"] = []

        points = item.get("summary", {}).get("results", [])
        for point in points:
            pred = point.get("prediction")
            if not pred:
                continue

            # Overall
            if pred.get("overall_risk"):
                groups[key]["overall"].append(pred["overall_risk"])
                groups[key]["probs"].append(pred.get("probability", 0))

            # Forecast theo ngày
            forecast = pred.get("forecast", {})
            for day in ["day_1", "day_2", "day_3"]:
                dp = forecast.get(day, {})
                if dp.get("risk_level"):
                    groups[key][day].append(dp["risk_level"])

    # Chuyển thành province-day records
    records = []
    for (date, province), g in groups.items():
        def is_alert(risk_list):
            if not risk_list:
                return None  # không có data
            alert_count = sum(1 for r in risk_list if r in ALERT_LABELS)
            return (alert_count / len(risk_list)) >= PROVINCE_ALERT_THRESHOLD

        records.append({
            "date":     date,
            "province": province,
            "overall":  is_alert(g["overall"]),
            "day_1":    is_alert(g["day_1"]),
            "day_2":    is_alert(g["day_2"]),
            "day_3":    is_alert(g["day_3"]),
            "avg_prob": round(sum(g["probs"]) / len(g["probs"]) * 100, 1)
                        if g["probs"] else 0.0,
            "n_points": len(g["overall"]),
        })

    return records


# ── Tính stats từ list province-days ────────────────────────────────────────
def calc_stats(records: list, bucket: str) -> dict:
    valid = [r for r in records if r[bucket] is not None]
    total = len(valid)
    if total == 0:
        return {"total": 0, "alert": 0, "alert_pct": 0.0, "avg_prob": 0.0}

    alert    = sum(1 for r in valid if r[bucket])
    avg_prob = round(sum(r["avg_prob"] for r in valid) / total, 1)
    return {
        "total":     total,
        "alert":     alert,
        "alert_pct": round(alert / total * 100, 1),
        "avg_prob":  avg_prob,
    }


# ── Tính TSS, CSI, F1 ────────────────────────────────────────────────────────
def calc_metrics(ev: dict, ctrl: dict) -> dict:
    """
    ev   = stats province-day của event thật  (label=1)
    ctrl = stats province-day của control sau (label=0)

    TP = event province-day bị cảnh báo
    FN = event province-day không bị cảnh báo
    FP = control province-day bị cảnh báo (false alarm)
    TN = control province-day không bị cảnh báo
    """
    if ev["total"] == 0 or ctrl["total"] == 0:
        return {"TSS": None, "CSI": None, "F1": None,
                "Sensitivity": None, "Specificity": None,
                "TP": 0, "FN": 0, "FP": 0, "TN": 0}

    TP = ev["alert"]
    FN = ev["total"] - ev["alert"]
    FP = ctrl["alert"]
    TN = ctrl["total"] - ctrl["alert"]

    sens = TP / (TP + FN) if (TP + FN) > 0 else 0
    spec = TN / (TN + FP) if (TN + FP) > 0 else 0
    tss  = round(sens + spec - 1, 3)
    csi  = round(TP / (TP + FP + FN), 3) if (TP + FP + FN) > 0 else 0
    f1   = round(2*TP / (2*TP + FP + FN), 3) if (2*TP + FP + FN) > 0 else 0

    return {
        "TP": TP, "FN": FN, "FP": FP, "TN": TN,
        "Sensitivity": round(sens, 3),
        "Specificity": round(spec, 3),
        "TSS": tss, "CSI": csi, "F1": f1,
    }


def tss_verdict(tss, bucket):
    if tss is None:
        return "N/A"
    if bucket in ("overall", "day_1"):
        if tss >= 0.5:   return "✅ TỐT (TSS ≥ 0.5)"
        elif tss >= 0.2: return "⚠️  KHÁ (TSS 0.2–0.5)"
        elif tss >= 0:   return "⚠️  YẾU (TSS 0–0.2)"
        else:            return "❌ CHƯA ĐẠT (TSS < 0)"
    elif bucket == "day_2":
        if tss >= 0.3:   return "✅ TỐT (TSS ≥ 0.3)"
        elif tss >= 0.1: return "⚠️  KHÁ (TSS 0.1–0.3)"
        elif tss >= 0:   return "⚠️  Suy giảm bình thường"
        else:            return "⚠️  Khó phân biệt 2 ngày — xem Limitations"
    else:  # day_3
        if tss >= 0.1:   return "✅ Còn tín hiệu (TSS ≥ 0.1)"
        elif tss >= 0:   return "⚠️  Suy giảm rõ ở 3 ngày — đặc tính tự nhiên"
        else:            return "⚠️  3 ngày khó dự báo — ghi Limitations"


# ── Đọc tất cả file → dict records ──────────────────────────────────────────
def load_all(folder: str) -> dict:
    """
    Trả về:
    {
        eid: {
            ftype: [province-day records]
        }
    }
    """
    result = {}
    for eid in EVENTS:
        result[eid] = {}
        for ftype in FILE_TYPES:
            suffix = "" if ftype == "event" else f"_{ftype}"
            path   = os.path.join(folder, f"{eid}{suffix}.json")
            data   = load_json(path)
            if data is None:
                continue
            result[eid][ftype] = parse_province_days(data)
    return result


# ── In báo cáo ───────────────────────────────────────────────────────────────
def print_report(all_data: dict):
    W = 74

    for bucket in BUCKETS:
        print(f"\n{'='*W}")
        print(f"  {BUCKET_LABELS[bucket]}")
        print(f"  Đơn vị: tỉnh-ngày | Ngưỡng cảnh báo: ≥{int(PROVINCE_ALERT_THRESHOLD*100)}% điểm MEDIUM+")
        print(f"{'='*W}")

        # ── Chi tiết từng event ──────────────────────────────────────
        total_ev_all   = {"total": 0, "alert": 0}
        total_ctrl_all = {"total": 0, "alert": 0}

        for eid in EVENTS:
            edata = all_data.get(eid, {})
            if "event" not in edata or "neg_after" not in edata:
                continue

            ev_stats   = calc_stats(edata["event"],    bucket)
            ctrl_stats = calc_stats(edata["neg_after"], bucket)
            m = calc_metrics(ev_stats, ctrl_stats)

            print(f"\n  {eid} {EVENT_NAMES.get(eid, eid)}")
            print(f"  {'─'*64}")
            print(f"  {'Loại':<22} {'Tỉnh-ngày':>10}  {'Cảnh báo':>12}  {'Prob TB':>8}")
            print(f"  {'─'*64}")

            for ftype, flabel in FILE_TYPES.items():
                if ftype not in edata:
                    continue
                s = calc_stats(edata[ftype], bucket)
                print(
                    f"  {flabel:<22} {s['total']:>10}  "
                    f"{s['alert']:>5} ({s['alert_pct']:>5.1f}%)  "
                    f"{s['avg_prob']:>7.1f}%"
                )

            print(f"  {'─'*64}")
            if m["TSS"] is not None:
                print(f"  TP={m['TP']}  FN={m['FN']}  FP={m['FP']}  TN={m['TN']}")
                print(f"  Sensitivity={m['Sensitivity']:.3f}  "
                      f"Specificity={m['Specificity']:.3f}  "
                      f"TSS={m['TSS']:.3f}  CSI={m['CSI']:.3f}  F1={m['F1']:.3f}")

            total_ev_all["total"] += ev_stats["total"]
            total_ev_all["alert"] += ev_stats["alert"]
            total_ctrl_all["total"] += ctrl_stats["total"]
            total_ctrl_all["alert"] += ctrl_stats["alert"]

        # ── Tổng kết ─────────────────────────────────────────────────
        total_ev_all["alert_pct"]   = round(
            total_ev_all["alert"]   / total_ev_all["total"]   * 100, 1
        ) if total_ev_all["total"] else 0
        total_ctrl_all["alert_pct"] = round(
            total_ctrl_all["alert"] / total_ctrl_all["total"] * 100, 1
        ) if total_ctrl_all["total"] else 0

        m_total = calc_metrics(total_ev_all, total_ctrl_all)

        print(f"\n  {'─'*64}")
        print(f"  TỔNG 8 SỰ KIỆN — PROVINCE-DAY LEVEL")
        print(f"  {'─'*64}")
        print(f"  Sự kiện thật : {total_ev_all['total']:>4} tỉnh-ngày  "
              f"→ {total_ev_all['alert']} cảnh báo ({total_ev_all['alert_pct']:.1f}%)")
        print(f"  Control sau  : {total_ctrl_all['total']:>4} tỉnh-ngày  "
              f"→ {total_ctrl_all['alert']} cảnh báo ({total_ctrl_all['alert_pct']:.1f}%)")

        if m_total["TSS"] is not None:
            print(f"\n  METRIC KHOA HỌC TỔNG HỢP (Allouche et al. 2006)")
            print(f"  {'─'*64}")
            print(f"  TP={m_total['TP']:>4}  FN={m_total['FN']:>4}  "
                  f"FP={m_total['FP']:>4}  TN={m_total['TN']:>4}")
            print(f"  Sensitivity (Recall) = {m_total['Sensitivity']:.3f}")
            print(f"  Specificity          = {m_total['Specificity']:.3f}")
            print(f"  TSS                  = {m_total['TSS']:.3f}  "
                  f"(tốt ≥ 0.5 | chấp nhận 0.2–0.5 | kém < 0.2)")
            print(f"  CSI (IoU)            = {m_total['CSI']:.3f}  "
                  f"(tốt ≥ 0.5 | chấp nhận 0.3–0.5 | kém < 0.3)")
            print(f"  F1-score             = {m_total['F1']:.3f}")
            print(f"\n  Kết luận: {tss_verdict(m_total['TSS'], bucket)}")

    # ── Ghi chú phương pháp ──────────────────────────────────────────
    print(f"\n{'='*W}")
    print("  GHI CHÚ PHƯƠNG PHÁP")
    print(f"{'='*W}")
    print(f"  Đơn vị đánh giá : Province-day (tỉnh × ngày)")
    print(f"  Ngưỡng cảnh báo : ≥ {int(PROVINCE_ALERT_THRESHOLD*100)}% điểm lưới trong tỉnh báo MEDIUM+")
    print(f"  Lý do           : Ground truth (White Book 2025) chỉ ghi nhận")
    print(f"                    ở cấp tỉnh — không có tọa độ ngập cụ thể.")
    print(f"                    Gán nhãn theo điểm lưới sẽ phạt oan model")
    print(f"                    ở vùng núi/cao nguyên trong cùng tỉnh.")
    print(f"  TSS             : True Skill Statistic (Allouche et al. 2006)")
    print(f"                    TSS = Sensitivity + Specificity - 1")
    print(f"                    Không bị ảnh hưởng bởi mất cân bằng dữ liệu")
    print(f"  CSI             : Critical Success Index (Lee et al. 2017)")
    print(f"                    CSI = TP / (TP + FP + FN)")
    print(f"  Control sau     : Cách event tối thiểu 10 ngày → hoàn lưu bão tan")
    print(f"  Control trước   : KHÔNG dùng làm nhãn 0 — tiền bão tích lũy bias")
    print(f"{'='*W}\n")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder",    "-f", default="benchmark_results")
    parser.add_argument("--threshold", "-t", type=float, default=0.30,
                        help="Ngưỡng tỉ lệ điểm MEDIUM+ để coi tỉnh-ngày là có lũ (default: 0.30)")
    parser.add_argument("--csv",       "-o", default=None)
    args = parser.parse_args()

    global PROVINCE_ALERT_THRESHOLD
    PROVINCE_ALERT_THRESHOLD = args.threshold

    all_data = load_all(args.folder)

    if not any(all_data.values()):
        print("Không tìm thấy file JSON nào trong:", args.folder)
        return

    print_report(all_data)

    # Lưu CSV tổng hợp nếu cần
    if args.csv:
        rows = []
        for eid, edata in all_data.items():
            for ftype, records in edata.items():
                for bucket in BUCKETS:
                    s = calc_stats(records, bucket)
                    rows.append({
                        "event": eid,
                        "event_name": EVENT_NAMES.get(eid, eid),
                        "type": ftype,
                        "bucket": bucket,
                        **s,
                    })
        pd.DataFrame(rows).to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"Đã lưu CSV: {args.csv}")


if __name__ == "__main__":
    main()
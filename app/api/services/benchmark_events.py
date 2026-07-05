BENCHMARK_EVENTS = [
    {
        "id": "E001",
        "name": "Flood after Typhoon No.1 (Wutip)",
        "start": "2025-06-10",
        "end":   "2025-06-14",
        "neg_before_date":       "2025-05-15",  # mùa khô, 26 ngày trước start
        "neg_after_date":        "2025-07-15",  # 31 ngày sau end, qua cao điểm mưa tháng 6
        "provinces":             ["quang_tri", "hue"],
        "neg_spatial_provinces": ["an_giang", "can_tho"],
    },
    {
        "id": "E002",
        "name": "Flood after Typhoon No.3 (Wipha)",
        "start": "2025-07-20",
        "end":   "2025-07-23",
        "neg_before_date":       "2025-07-05",  # giữ nguyên, đủ sạch
        "neg_after_date":        "2025-08-25",  # 33 ngày sau end, tránh E003 start 24/08 → dùng 25/08
        "provinces":             ["hung_yen", "ninh_binh", "thanh_hoa", "nghe_an"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau"],
    },
    {
        "id": "E003",
        "name": "Flood after Typhoon No.5 (Kajiki)",
        "start": "2025-08-24",
        "end":   "2025-08-27",
        "neg_before_date":       "2025-08-13",  # giữ nguyên
        "neg_after_date":        "2025-09-15",  # giữ nguyên, 19 ngày sau end → OK
        "provinces":             ["thanh_hoa", "nghe_an", "ha_tinh", "ninh_binh",
                                  "ha_noi", "bac_ninh", "quang_ninh", "phu_tho"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau", "dong_thap"],
    },
    {
        "id": "E004",
        "name": "Flood after Typhoon No.10 (Bualoi)",
        "start": "2025-09-27",
        "end":   "2025-10-02",
        "neg_before_date":       "2025-09-15",  # 12 ngày trước, sau E003 neg_after 15/09 → sát nhưng khác tỉnh
        "neg_after_date":        "2025-10-19",  # giữ nguyên, sau E005 end 07/10 → OK
        "provinces":             ["thanh_hoa", "nghe_an", "ha_tinh", "hue"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau"],
    },
    {
        "id": "E005",
        "name": "Flood after Typhoon No.11 (Matmo)",
        "start": "2025-10-06",
        "end":   "2025-10-07",
        "neg_before_date":       "2025-09-15",  # dùng chung với E004, khác tỉnh → OK
        "neg_after_date":        "2025-10-19",  # giữ nguyên
        "provinces":             ["thai_nguyen", "bac_ninh", "ha_noi", "tuyen_quang",
                                  "lang_son", "cao_bang", "quang_ninh", "phu_tho"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau", "dong_thap"],
    },
    {
        "id": "E006",
        "name": "Flood after Typhoon No.12 (FengShen)",
        "start": "2025-10-22",
        "end":   "2025-11-03",
        "neg_before_date":       "2025-10-12",  # giữ nguyên
        "neg_after_date":        "2025-11-20",  # 17 ngày sau end, sau E007 start 16/11 → dùng tỉnh khác E007
        "provinces":             ["quang_tri", "hue", "da_nang", "quang_ngai"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau"],
    },
    {
        "id": "E007",
        "name": "Central Vietnam Heavy Rain Event",
        "start": "2025-11-16",
        "end":   "2025-11-22",
        "neg_before_date":       "2025-11-06",  # giữ nguyên
        "neg_after_date":        "2025-12-10",  # 18 ngày sau end, tháng 12 miền Trung ít mưa hơn
        "provinces":             ["dak_lak", "gia_lai", "khanh_hoa", "lam_dong"],
        "neg_spatial_provinces": ["ha_noi", "bac_ninh", "hung_yen"],
    },
    {
        "id": "E008",
        "name": "Upper Ma River Flood",
        "start": "2025-07-28",
        "end":   "2025-08-02",
        "neg_before_date":       "2025-07-10",  # 18 ngày trước, mùa mưa nhưng chưa có bão
        "neg_after_date":        "2025-09-05",  # 34 ngày sau end, tránh xa mùa cao điểm tháng 8
        "provinces":             ["son_la"],
        "neg_spatial_provinces": ["an_giang", "can_tho"],
    },
    # E009 Flash Flood Điện Biên Đông → BỎ vì là lũ quét cục bộ,
    # không phù hợp với model dự báo lũ lụt diện rộng grid 0.1°
]
BENCHMARK_EVENTS = [
    {
        "id": "E001",
        "name": "Flood after Typhoon No.1 (Wutip)",
        "start": "2025-06-10",
        "end":   "2025-06-14",
        "neg_before_date":       "2025-05-31",  # 10 ngày trước start
        "neg_after_date":        "2025-06-24",  # 10 ngày sau end
        "provinces":             ["quang_tri", "hue"],
        "neg_spatial_provinces": ["an_giang", "can_tho"],
    },
    {
        "id": "E002",
        "name": "Flood after Typhoon No.3 (Wipha)",
        "start": "2025-07-20",
        "end":   "2025-07-23",
        "neg_before_date":       "2025-07-10",  # 10 ngày trước start
        "neg_after_date":        "2025-08-02",  # 10 ngày sau end (khác tỉnh E008 nên không đụng)
        "provinces":             ["hung_yen", "ninh_binh", "thanh_hoa", "nghe_an"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau"],
    },
    {
        "id": "E003",
        "name": "Flood after Typhoon No.5 (Kajiki)",
        "start": "2025-08-24",
        "end":   "2025-08-27",
        "neg_before_date":       "2025-08-14",  # 10 ngày trước start
        "neg_after_date":        "2025-09-06",  # 10 ngày sau end
        "provinces":             ["thanh_hoa", "nghe_an", "ha_tinh", "ninh_binh",
                                  "ha_noi", "bac_ninh", "quang_ninh", "phu_tho"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau", "dong_thap"],
    },
    {
        "id": "E004",
        "name": "Flood after Typhoon No.10 (Bualoi)",
        "start": "2025-09-27",
        "end":   "2025-10-02",
        "neg_before_date":       "2025-09-17",  # 10 ngày trước start, sau E003 neg_after (06/09) đủ xa
        "neg_after_date":        "2025-10-12",  # 10 ngày sau end, trước E006 start (22/10) đủ xa
        "provinces":             ["thanh_hoa", "nghe_an", "ha_tinh", "hue"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau"],
    },
    {
        "id": "E005",
        "name": "Flood after Typhoon No.11 (Matmo)",
        "start": "2025-10-06",
        "end":   "2025-10-07",
        "neg_before_date":       "2025-09-26",  # 10 ngày trước start (khác tỉnh E004 nên không đụng)
        "neg_after_date":        "2025-10-17",  # 10 ngày sau end
        "provinces":             ["thai_nguyen", "bac_ninh", "ha_noi", "tuyen_quang",
                                  "lang_son", "cao_bang", "quang_ninh", "phu_tho"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau", "dong_thap"],
    },
    {
        "id": "E006",
        "name": "Flood after Typhoon No.12 (FengShen)",
        "start": "2025-10-22",
        "end":   "2025-11-03",
        "neg_before_date":       "2025-10-12",  # 10 ngày trước start, sau E004 neg_after (12/10) vừa khít
        "neg_after_date":        "2025-11-13",  # 10 ngày sau end, trước E007 start (16/11) đủ xa
        "provinces":             ["quang_tri", "hue", "da_nang", "quang_ngai"],
        "neg_spatial_provinces": ["an_giang", "can_tho", "ca_mau"],
    },
    {
        "id": "E007",
        "name": "Central Vietnam Heavy Rain Event",
        "start": "2025-11-16",
        "end":   "2025-11-22",
        "neg_before_date":       "2025-11-06",  # 10 ngày trước start
        "neg_after_date":        "2025-12-02",  # 10 ngày sau end
        "provinces":             ["dak_lak", "gia_lai", "khanh_hoa", "lam_dong"],
        "neg_spatial_provinces": ["ha_noi", "bac_ninh", "hung_yen"],
    },
    {
        "id": "E008",
        "name": "Upper Ma River Flood",
        "start": "2025-07-28",
        "end":   "2025-08-02",
        "neg_before_date":       "2025-07-18",  # 10 ngày trước start
        "neg_after_date":        "2025-08-12",  # 10 ngày sau end
        "provinces":             ["son_la"],
        "neg_spatial_provinces": ["an_giang", "can_tho"],
    },
    # E009 Flash Flood Điện Biên Đông → LOẠI vì là lũ quét cục bộ (địa hình dốc, vài giờ),
    # không phù hợp model dự báo lũ lụt diện rộng ở độ phân giải grid 0.1° (~11km).
]
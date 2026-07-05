# run_benchmark.py
from app.api.services.benchmark_service import benchmark_all_events

if __name__ == "__main__":
    summary = benchmark_all_events()
    print("\n=== TỔNG KẾT ===")
    print(f"Tổng events: {summary['total_events']}")
    print(f"Thành công: {summary['success']}")
    print(f"Thất bại: {summary['failed']}")
    for r in summary["results"]:
        print(f"  - {r['event_id']}: {r['status']}")
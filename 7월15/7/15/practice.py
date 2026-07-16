import json
import sys
from pathlib import Path
from collections import Counter, defaultdict


# =========================================================
# JSON 데이터 불러오기
# =========================================================

json_path = Path(__file__).parent / "Python_Practice1_Data.json"

with json_path.open("r", encoding="utf-8") as file:
    sales = json.load(file)


# =========================================================
# 1. 리스트·딕셔너리 컴프리헨션
# amount >= 1000 거래 필터링
# 지역별 총매출 계산
# =========================================================

filtered_sales = [
    item
    for item in sales
    if item["amount"] >= 1000
]

regions = {
    item["region"]
    for item in filtered_sales
}

region_total = {
    region: sum(
        item["amount"]
        for item in filtered_sales
        if item["region"] == region
    )
    for region in regions
}

# 계산 결과 자체를 검증하는 기본 assert
assert sum(region_total.values()) == sum(
    item["amount"] for item in filtered_sales
)

print("1. amount >= 1000인 거래")

for item in filtered_sales:
    print(item)

print("\n지역별 총매출")

for region, total in sorted(region_total.items()):
    print(f"{region}: {total}")


# =========================================================
# 2. Counter + defaultdict
# Counter로 지역별 거래 건수
# defaultdict로 카테고리별 amount 리스트
# =========================================================

region_count = Counter(
    item["region"]
    for item in sales
)

category_amounts = defaultdict(list)

for item in sales:
    category_amounts[item["category"]].append(item["amount"])

expected_count = [
    ("서울", 14),
    ("부산", 13),
    ("대구", 13),
    ("인천", 12),
    ("광주", 12),
    ("대전", 12),
    ("울산", 12),
    ("세종", 12),
]

assert region_count.most_common() == expected_count

print("\n2. 지역별 거래 건수")
print(region_count.most_common())

print("\n카테고리별 amount 리스트")
print(dict(category_amounts))


# =========================================================
# 3. 제너레이터와 리스트의 메모리 비교
# amount > 1000인 거래만 yield
# =========================================================

def filter_large_amount(items):
    """amount가 1000보다 큰 거래를 하나씩 반환한다."""
    for item in items:
        if item["amount"] > 1000:
            yield item


filtered_list = [
    item
    for item in sales
    if item["amount"] > 1000
]

filtered_generator = filter_large_amount(sales)

list_size = sys.getsizeof(filtered_list)
generator_size = sys.getsizeof(filtered_generator)

assert generator_size < list_size

print("\n3. 메모리 크기 비교")
print(f"리스트 메모리 크기: {list_size} bytes")
print(f"제너레이터 메모리 크기: {generator_size} bytes")
print(f"메모리 차이: {list_size - generator_size} bytes")

print(f"\n리스트 결과 개수: {len(filtered_list)}")

print("\n제너레이터 결과")

for item in filtered_generator:
    print(item)


# =========================================================
# 4. 월별·카테고리별 총매출 집계
# defaultdict + 딕셔너리 컴프리헨션
# =========================================================

monthly_totals = defaultdict(lambda: defaultdict(int))

for item in sales:
    month = item["month"]
    category = item["category"]
    amount = item["amount"]

    monthly_totals[month][category] += amount

monthly_category_sales = {
    month: {
        category: total
        for category, total in categories.items()
    }
    for month, categories in monthly_totals.items()
}

print("\n4. 월별 카테고리 매출 집계")

for month, categories in sorted(monthly_category_sales.items()):
    print(f"\n{month}")

    for category, total in sorted(categories.items()):
        print(f"{category}: {total}")


# =========================================================
# 5. 금액 기준 top3 내림차순 정렬
# =========================================================

top3 = sorted(
    sales,
    key=lambda item: item["amount"],
    reverse=True
)[:3]

assert top3 == sorted(
    top3,
    key=lambda item: item["amount"],
    reverse=True
)

print("\n5. 금액 기준 TOP 3")

for rank, item in enumerate(top3, start=1):
    print(
        f"{rank}위: "
        f"{item['region']} / "
        f"{item['category']} / "
        f"{item['month']} / "
        f"{item['amount']}"
    )
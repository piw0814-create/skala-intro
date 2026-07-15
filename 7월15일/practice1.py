#Python_Practice1_Data.json(Sales)리스트에서
#1 amount ≥ 1000인 거래만 필터링하고,
#2 지역별 총매출 dict를 컴프리헨션으로계산

import json
from pathlib import Path

json_path = Path(__file__).parent / "Python_Practice1_Data.json"

with json_path.open("r", encoding="utf-8") as file:
    sales = json.load(file)

# amount가 1000 이상인 거래 필터링
filtered_sales = [
    item for item in sales
    if item["amount"] >= 1000
]

# 필터링된 거래의 지역별 총매출
regions = {item["region"] for item in filtered_sales}

region_total = {
    region: sum(
        item["amount"]
        for item in filtered_sales
        if item["region"] == region
    )
    for region in regions
}

print("필터링된 거래")
for item in filtered_sales:
    print(item)

print("\n지역별 총매출")
for region, total in sorted(region_total.items()):
    print(f"{region}: {total}")

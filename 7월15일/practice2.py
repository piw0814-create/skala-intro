#Counter로 지역별 거래 건수를, defaultdict로 카테고리별 amount 리스트

import json
from pathlib import Path
from collections import Counter, defaultdict

json_path = Path(__file__).parent / "Python_Practice1_Data.json"

with json_path.open("r", encoding="utf-8") as file:
    data = json.load(file)

# Counter로 지역별 거래 건수
region_count = Counter(
    item["region"] for item in data
)

# defaultdict로 카테고리별 amount 리스트
category_amounts = defaultdict(list)

for item in data:
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

print("지역별 거래 건수")
print(region_count.most_common())

print("\n카테고리별 amount 리스트")
print(dict(category_amounts))
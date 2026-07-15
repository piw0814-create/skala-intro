#sales 데이터를 month·category 기준으로 그룹핑해 총매출 dict를 완성 (컴프리헨션 + defaultdict)
import json
from pathlib import Path
from collections import defaultdict

json_path = Path(__file__).parent / "Python_Practice1_Data.json"

with json_path.open("r", encoding="utf-8") as file:
    data = json.load(file)


monthly_totals = defaultdict(lambda: defaultdict(int))

for item in data:
    monthly_totals[item["month"]][item["category"]] += item["amount"]


monthly_category_sales = {
    month: {
        category: total
        for category, total in categories.items()
    }
    for month, categories in monthly_totals.items()
}


print("월별 카테고리 매출 집계")

for month, categories in sorted(monthly_category_sales.items()):
    print(f"\n{month}")

    for category, total in sorted(categories.items()):
        print(f"{category}: {total}")
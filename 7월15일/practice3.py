#amount > 1000 인 행만 yield 하는 제너레이터를 작성하고, 리스트 버전과 메모리 크기를 비교
import json
import sys
from pathlib import Path

json_path = Path(__file__).parent / "Python_Practice1_Data.json"

with json_path.open("r", encoding="utf-8") as file:
    data = json.load(file)


def filter_large_amount(items):
    """amount가 1000보다 큰 거래를 하나씩 반환한다."""
    for item in items:
        if item["amount"] > 1000:
            yield item


# 리스트 버전
filtered_list = [
    item for item in data
    if item["amount"] > 1000
]

# 제너레이터 버전
filtered_generator = filter_large_amount(data)

list_size = sys.getsizeof(filtered_list)
generator_size = sys.getsizeof(filtered_generator)

assert generator_size < list_size

print("리스트 메모리 크기:", list_size, "bytes")
print("제너레이터 메모리 크기:", generator_size, "bytes")
print("메모리 차이:", list_size - generator_size, "bytes")

print("\n리스트 결과 개수:", len(filtered_list))

print("\n제너레이터 결과")
for item in filtered_generator:
    print(item)
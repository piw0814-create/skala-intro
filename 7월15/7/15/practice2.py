"""
Python Practice 2 - 판매 데이터 검증 및 저장 프로그램
작성자 : 4반 박인우
JSON 형식의 판매 데이터를 안전하게 읽고, Pydantic의 SalesRecord 모델을
사용해 각 데이터를 검증하는 프로그램. 
month와 region은 빈 값을 허용하지 않고 amount는 0보다 큰 값만 허용하도록 설정. 
category는 선택 항목으로 처리.

검증에 성공한 데이터는 valid 목록에, 실패한 데이터는 원본 행과 오류내용을 포함한 errors 목록에 분리. 
valid 데이터는 model_dump()를 사용해 CSV 파일로 저장하고, errors 데이터는 한글이 깨지지 않도록 ensure_ascii=False를 적용해 JSON 파일로 저장.

파일이 없거나 JSON 형식이 잘못된 경우를 대비해 try-except-finally와 로깅을 적용, 저장 과정과 재로딩 과정에도 입출력 예외 처리를 추가.
마지막에는 저장된 CSV와 JSON 파일을 다시 읽어 저장 전후의 데이터 건수가 같은지 assert로 검증.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


# =========================================================
# 로깅 및 파일 경로 설정
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent

INPUT_FILE = BASE_DIR / "Python_Practice2_Data.json"
VALID_FILE = BASE_DIR / "valid_sales.csv"
ERROR_FILE = BASE_DIR / "sales_errors.json"


# =========================================================
# 1. 파일 읽기
# =========================================================

def safe_load_csv(
    file_path: Path,
) -> list[dict[str, Any]] | None:
    """
    JSON 파일을 안전하게 읽어 딕셔너리 리스트로 반환한다.

    파일이 없거나 JSON 형식이 잘못된 경우 logger.error를 남기고
    None을 반환한다. 성공 여부와 관계없이 '로딩 종료'를 출력한다.

    Args:
        file_path: 읽을 JSON 파일 경로

    Returns:
        JSON에서 읽은 딕셔너리 리스트 또는 None
    """

    try:
        with file_path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

        if not isinstance(raw_data, list):
            logger.error("JSON 최상위 데이터가 리스트가 아닙니다.")
            return None

        if not all(isinstance(row, dict) for row in raw_data):
            logger.error("JSON 리스트에 딕셔너리가 아닌 데이터가 있습니다.")
            return None

        logger.info("파일 로딩 성공: %d건", len(raw_data))
        return raw_data

    except FileNotFoundError:
        logger.error("파일을 찾을 수 없습니다: %s", file_path)
        return None

    except json.JSONDecodeError as error:
        logger.error("JSON 형식 오류: %s", error)
        return None

    except OSError as error:
        logger.error("파일 읽기 오류: %s", error)
        return None

    finally:
        print("로딩 종료")


# =========================================================
# 2. Pydantic v2 스키마
# =========================================================

class SalesRecord(BaseModel):
    """
    판매 데이터 한 행을 표현하는 Pydantic 모델.

    - month, region: 빈 문자열 불가
    - amount: 0보다 커야 함
    - category: 생략 가능
    """

    month: str
    region: str
    amount: float = Field(gt=0)
    category: str | None = None

    @field_validator("month", "region")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        """month와 region의 공백 및 빈 문자열을 검증한다."""

        value = value.strip()

        if not value:
            raise ValueError("비어 있을 수 없습니다.")

        return value

    @field_validator("category")
    @classmethod
    def normalize_category(
        cls,
        value: str | None,
    ) -> str | None:
        """빈 category 값을 None으로 정규화한다."""

        if value is None:
            return None

        value = value.strip()
        return value or None


# =========================================================
# 3. 검증 파이프라인
# =========================================================

def validate_sales(
    raw_data: list[dict[str, Any]],
) -> tuple[list[SalesRecord], list[dict[str, Any]]]:
    """
    원본 데이터를 SalesRecord로 변환하고 검증한다.

    검증 성공 데이터는 valid에 저장하고,
    ValidationError가 발생한 데이터는 원본 행과 오류 내용을
    errors 리스트에 저장한다.

    Args:
        raw_data: JSON에서 읽은 원본 딕셔너리 리스트

    Returns:
        valid와 errors로 구성된 튜플
    """

    valid: list[SalesRecord] = []
    errors: list[dict[str, Any]] = []

    for row_number, row in enumerate(raw_data, start=1):
        try:
            record = SalesRecord.model_validate(row)
            valid.append(record)

        except ValidationError as error:
            print(f"\n{row_number}번째 행 ValidationError")
            print(error)

            errors.append(
                {
                    "row": row,
                    "error": error.errors(include_context=False),
                }
            )

    return valid, errors


# =========================================================
# 4. 결과 파일 저장
# =========================================================

def save_valid_csv(
    records: list[SalesRecord],
    file_path: Path,
) -> bool:
    """
    검증에 성공한 SalesRecord 목록을 CSV로 저장한다.

    각 모델은 model_dump()를 이용해 딕셔너리로 변환한다.

    Returns:
        저장 성공 여부
    """

    fieldnames = [
        "month",
        "region",
        "amount",
        "category",
    ]

    try:
        with file_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            writer.writerows(
                record.model_dump()
                for record in records
            )

        logger.info(
            "정상 데이터 CSV 저장 완료: %d건",
            len(records),
        )
        return True

    except OSError as error:
        logger.error("CSV 저장 실패: %s", error)
        return False


def save_errors_json(
    errors: list[dict[str, Any]],
    file_path: Path,
) -> bool:
    """
    검증 실패 데이터를 JSON 파일로 저장한다.

    ensure_ascii=False를 사용해 한글이 유니코드 이스케이프
    문자열로 저장되지 않도록 한다.

    Returns:
        저장 성공 여부
    """

    try:
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(
                errors,
                file,
                ensure_ascii=False,
                indent=4,
            )

        logger.info(
            "오류 데이터 JSON 저장 완료: %d건",
            len(errors),
        )
        return True

    except (OSError, TypeError) as error:
        logger.error("오류 JSON 저장 실패: %s", error)
        return False


# =========================================================
# 5. 저장 파일 재로딩
# =========================================================

def reload_valid_csv(
    file_path: Path,
) -> list[dict[str, str]] | None:
    """
    저장된 CSV 파일을 다시 읽어 딕셔너리 리스트로 반환한다.
    """

    try:
        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            return list(csv.DictReader(file))

    except OSError as error:
        logger.error("CSV 재로딩 실패: %s", error)
        return None


def reload_errors_json(
    file_path: Path,
) -> list[dict[str, Any]] | None:
    """
    저장된 오류 JSON 파일을 다시 읽어 리스트로 반환한다.
    """

    try:
        with file_path.open("r", encoding="utf-8") as file:
            loaded_data = json.load(file)

        if not isinstance(loaded_data, list):
            logger.error("오류 JSON 최상위 데이터가 리스트가 아닙니다.")
            return None

        return loaded_data

    except FileNotFoundError:
        logger.error("오류 JSON 파일을 찾을 수 없습니다: %s", file_path)
        return None

    except json.JSONDecodeError as error:
        logger.error("오류 JSON 형식 오류: %s", error)
        return None

    except OSError as error:
        logger.error("오류 JSON 재로딩 실패: %s", error)
        return None


# =========================================================
# 프로그램 실행
# =========================================================

def main() -> None:
    """전체 판매 데이터 검증 및 저장 파이프라인을 실행한다."""

    # 없는 파일을 읽었을 때 None을 반환하는지 확인한다.
    missing_file = BASE_DIR / "not_found.json"

    assert safe_load_csv(missing_file) is None
    print("safe_load_csv 동작 + assert None 통과")

    # 제공된 JSON 파일을 읽는다.
    raw_data = safe_load_csv(INPUT_FILE)

    if raw_data is None:
        logger.error("원본 데이터 로딩에 실패하여 프로그램을 종료합니다.")
        return

    # 원본 데이터를 Pydantic 모델로 검증한다.
    valid, errors = validate_sales(raw_data)

    # 모든 원본 행이 valid 또는 errors에 포함됐는지 확인한다.
    assert len(valid) + len(errors) == len(raw_data)

    print(
        "\n검증 결과\n"
        f"- 전체 데이터: {len(raw_data)}건\n"
        f"- valid: {len(valid)}건\n"
        f"- errors: {len(errors)}건"
    )

    print(
        f"valid {len(valid)}건 / "
        f"errors {len(errors)}건 assert 통과"
    )

    if errors:
        print("\nValidationError 내용")

        for error_item in errors:
            print(error_item)
    else:
        print("ValidationError 없음")

    # 정상 데이터와 오류 데이터를 각각 저장한다.
    valid_saved = save_valid_csv(valid, VALID_FILE)
    errors_saved = save_errors_json(errors, ERROR_FILE)

    if not valid_saved or not errors_saved:
        logger.error("결과 파일 저장에 실패했습니다.")
        return

    # 저장된 파일을 다시 읽는다.
    reloaded = reload_valid_csv(VALID_FILE)
    reloaded_errors = reload_errors_json(ERROR_FILE)

    if reloaded is None or reloaded_errors is None:
        logger.error("저장 파일 재로딩에 실패했습니다.")
        return

    # 저장 전후 데이터 건수가 같은지 확인한다.
    assert len(reloaded) == len(valid)
    assert len(reloaded_errors) == len(errors)

    print(
        "\n재로딩 결과\n"
        f"- CSV 재로딩: {len(reloaded)}건\n"
        f"- JSON 재로딩: {len(reloaded_errors)}건"
    )

    print(
        f"재로딩 후 len(reloaded) == "
        f"{len(valid)} 통과"
    )


if __name__ == "__main__":
    main()
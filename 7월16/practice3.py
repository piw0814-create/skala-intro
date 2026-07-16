"""
프로그램명: 판매 데이터 분석 및 데이터 도구 성능 비교
작성자: 4반 박인우
작성일: 2026-07-16
입력 파일: sales_100k.csv

프로그램 설명:
판매 데이터를 Pandas로 탐색하고 IQR 방법으로 이상치를 제거한다.
이후 region·category별 총매출, 평균, 거래 건수를
Pandas, Polars Lazy API, DuckDB SQL로 각각 계산한다.
마지막으로 timeit을 이용해 세 도구의 실행 시간을 비교한다.

처리 흐름:
1. 입력 파일과 필수 컬럼 검증
2. Pandas 기본 EDA 및 IQR 이상치 처리
3. Pandas named aggregation
4. Polars Lazy API 집계
5. DuckDB SQL 집계
6. 세 도구의 실행 시간 비교
"""

from pathlib import Path
import timeit

import duckdb
import pandas as pd
import polars as pl


# --------------------------------------------------
# 공통 설정
# --------------------------------------------------

FILE_PATH = Path("sales_100k.csv")
REQUIRED_COLUMNS = {"region", "category", "amount"}
BENCHMARK_NUMBER = 3

# --------------------------------------------------
# 1. Pandas 데이터 로딩 및 기본 검증
# --------------------------------------------------

def load_sales_data(file_path: Path) -> pd.DataFrame:
    """
    판매 CSV 파일을 불러오고 필수 컬럼 존재 여부를 검증한다.

    Args:
        file_path: 분석할 CSV 파일 경로

    Returns:
        검증이 완료된 Pandas DataFrame

    Raises:
        FileNotFoundError: CSV 파일이 존재하지 않을 때
        ValueError: 파일이 비어 있거나 필수 컬럼이 없을 때
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"CSV 파일을 찾을 수 없습니다: {file_path.resolve()}"
        )

    try:
        df = pd.read_csv(file_path)

    except pd.errors.EmptyDataError as error:
        raise ValueError("CSV 파일이 비어 있습니다.") from error

    except pd.errors.ParserError as error:
        raise ValueError("CSV 파일 형식을 해석할 수 없습니다.") from error

    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"필수 컬럼이 없습니다: {sorted(missing_columns)}"
        )

    return df

# --------------------------------------------------
# 2. IQR 기준 이상치 제거
# --------------------------------------------------

def remove_amount_outliers(df: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    """
    amount 컬럼의 IQR 정상 범위를 계산하고 이상치와 결측치를 제외한다.

    Args:
        df: 판매 데이터가 담긴 Pandas DataFrame

    Returns:
        이상치가 제거된 DataFrame, IQR 하한, IQR 상한

    Raises:
        ValueError: amount에 유효한 숫자값이 없거나
                    필터 후 데이터가 남지 않았을 때
    """
    valid_amount = df["amount"].dropna()

    if valid_amount.empty:
        raise ValueError("amount 컬럼에 유효한 숫자값이 없습니다.")

    q1 = valid_amount.quantile(0.25)
    q3 = valid_amount.quantile(0.75)
    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    if iqr == 0:
        print("[경고] IQR이 0입니다. amount 값의 분포를 확인하세요.")

    # between()이 True인 행은 IQR 기준 정상 범위다.
    normal_mask = df["amount"].between(lower_bound, upper_bound)

    # 결측치는 이상치와 구분해서 별도로 계산한다.
    outlier_mask = df["amount"].notna() & ~normal_mask
    missing_mask = df["amount"].isna()

    df_clean = df.loc[normal_mask].copy()

    if df_clean.empty:
        raise ValueError("IQR 필터 후 분석할 데이터가 남아 있지 않습니다.")

    print("\n[IQR 이상치 처리]")
    print(f"Q1: {q1:,.2f}")
    print(f"Q3: {q3:,.2f}")
    print(f"IQR: {iqr:,.2f}")
    print(f"정상 범위: {lower_bound:,.2f} ~ {upper_bound:,.2f}")
    print(f"제거 전 행 수: {len(df):,}")
    print(f"이상치 행 수: {outlier_mask.sum():,}")
    print(f"amount 결측 행 수: {missing_mask.sum():,}")
    print(f"제거 후 행 수: {len(df_clean):,}")

    return df_clean, lower_bound, upper_bound

# --------------------------------------------------
# 3. Pandas named aggregation
# --------------------------------------------------

def aggregate_with_pandas(df: pd.DataFrame) -> pd.DataFrame:
    """
    region·category별 총매출, 평균매출, 거래 건수를 계산한다.

    Args:
        df: IQR 이상치가 제거된 Pandas DataFrame

    Returns:
        total 기준 내림차순으로 정렬된 집계 DataFrame

    Raises:
        ValueError: 집계할 데이터가 비어 있을 때
    """
    if df.empty:
        raise ValueError("Pandas로 집계할 데이터가 없습니다.")

    # 결측 범주를 유지하여 집계 과정에서 행이 제외되지 않도록 한다.
    group_source = df.assign(
        region=df["region"].fillna("미상"),
        category=df["category"].fillna("미분류"),
    )

    summary = (
        group_source
        .groupby(["region", "category"], as_index=False)
        .agg(
            total=("amount", "sum"),
            mean=("amount", "mean"),
            count=("amount", "count"),
        )
        .sort_values("total", ascending=False, ignore_index=True)
    )

    return summary

# --------------------------------------------------
# 4. Polars Lazy API 집계
# --------------------------------------------------

def aggregate_with_polars(
    file_path: Path,
    lower_bound: float,
    upper_bound: float,
) -> pl.DataFrame:
    """
    Polars Lazy API로 IQR 정상 데이터를 필터링하고
    region·category별 매출을 집계한다.

    Returns:
        collect()가 완료된 Polars DataFrame
    """
    try:
        result = (
            pl.scan_csv(
                file_path,
                schema_overrides={"amount": pl.Float64},
            )
            .filter(
                pl.col("amount").is_not_null()
                & (pl.col("amount") >= lower_bound)
                & (pl.col("amount") <= upper_bound)
            )
            .group_by(
                pl.col("region").fill_null("미상").alias("region"),
                pl.col("category").fill_null("미분류").alias("category"),
            )
            .agg(
                pl.col("amount").sum().alias("total"),
                pl.col("amount").mean().alias("mean"),
                pl.len().alias("count"),
            )
            .sort("total", descending=True)
            .collect()
        )

        return result

    except pl.exceptions.PolarsError as error:
        raise RuntimeError(
            f"Polars 집계 실행에 실패했습니다: {error}"
        ) from error

# --------------------------------------------------
# 5. DuckDB SQL 집계
# --------------------------------------------------

def aggregate_with_duckdb(
    file_path: Path,
    lower_bound: float,
    upper_bound: float,
) -> pd.DataFrame:
    """
    DuckDB SQL로 IQR 정상 데이터를 필터링하고
    region·category별 매출을 집계한다.

    Args:
        file_path: 분석할 CSV 파일 경로
        lower_bound: IQR 정상 범위 하한
        upper_bound: IQR 정상 범위 상한

    Returns:
        DuckDB 집계 결과를 변환한 Pandas DataFrame

    Raises:
        RuntimeError: SQL 실행에 실패했을 때
    """
    # SQL 문자열 안에서 파일 경로의 작은따옴표가 문제되지 않도록 처리한다.
    safe_path = str(file_path).replace("'", "''")

    query = f"""
        SELECT
            COALESCE(region, '미상') AS region,
            COALESCE(category, '미분류') AS category,
            SUM(amount) AS total,
            AVG(amount) AS mean,
            COUNT(amount) AS count
        FROM read_csv_auto('{safe_path}')
        WHERE amount BETWEEN {lower_bound} AND {upper_bound}
        GROUP BY region, category
        ORDER BY total DESC
    """

    connection = duckdb.connect()

    try:
        result = connection.execute(query).df()
        return result

    except duckdb.Error as error:
        raise RuntimeError(
            f"DuckDB SQL 집계 실행에 실패했습니다: {error}"
        ) from error

    finally:
        connection.close()

# --------------------------------------------------
# 6. 세 도구 집계 결과 검증
# --------------------------------------------------

def validate_results(
    pandas_result: pd.DataFrame,
    polars_result: pl.DataFrame,
    duckdb_result: pd.DataFrame,
) -> None:
    """
    Pandas·Polars·DuckDB의 집계 결과가 동일한지 검증한다.

    평균값은 부동소수점 계산 과정에서 미세한 차이가 생길 수 있으므로
    작은 오차를 허용하여 비교한다.

    Raises:
        RuntimeError: 세 도구의 결과가 일치하지 않을 때
    """
    # PyArrow 설치 여부와 관계없이 비교할 수 있도록 dict를 거쳐 변환한다.
    polars_to_pandas = pd.DataFrame(polars_result.to_dicts())

    compare_columns = ["region", "category", "total", "mean", "count"]

    pandas_check = (
        pandas_result[compare_columns]
        .sort_values(["region", "category"])
        .reset_index(drop=True)
    )

    polars_check = (
        polars_to_pandas[compare_columns]
        .sort_values(["region", "category"])
        .reset_index(drop=True)
    )

    duckdb_check = (
        duckdb_result[compare_columns]
        .sort_values(["region", "category"])
        .reset_index(drop=True)
    )

    try:
        pd.testing.assert_frame_equal(
            pandas_check,
            polars_check,
            check_dtype=False,
            check_exact=False,
            rtol=1e-9,
            atol=1e-6,
        )

        pd.testing.assert_frame_equal(
            pandas_check,
            duckdb_check,
            check_dtype=False,
            check_exact=False,
            rtol=1e-9,
            atol=1e-6,
        )

    except AssertionError as error:
        raise RuntimeError(
            "Pandas·Polars·DuckDB의 집계 결과가 일치하지 않습니다."
        ) from error

    print("\n[결과 검증]")
    print("Pandas·Polars·DuckDB의 집계 결과가 모두 일치합니다.")

# --------------------------------------------------
# 7. 세 도구 실행 시간 비교
# --------------------------------------------------

def run_pandas_pipeline(
    file_path: Path,
    lower_bound: float,
    upper_bound: float,
) -> pd.DataFrame:
    """
    성능 비교를 위해 CSV 로딩부터 Pandas 집계까지 전체 과정을 실행한다.
    """
    df = pd.read_csv(
        file_path,
        usecols=["region", "category", "amount"],
    )

    normal_mask = df["amount"].between(
        lower_bound,
        upper_bound,
    )
    df_clean = df.loc[normal_mask].copy()

    return aggregate_with_pandas(df_clean)

def benchmark_tools(
    file_path: Path,
    lower_bound: float,
    upper_bound: float,
) -> dict[str, float]:
    """
    Pandas·Polars·DuckDB의 전체 실행 시간을 동일 횟수로 측정한다.

    Returns:
        도구별 전체 실행 시간이 담긴 딕셔너리

    Raises:
        RuntimeError: 성능 측정 도중 오류가 발생했을 때
    """
    try:
        pandas_time = timeit.timeit(
            lambda: run_pandas_pipeline(
                file_path,
                lower_bound,
                upper_bound,
            ),
            number=BENCHMARK_NUMBER,
        )

        polars_time = timeit.timeit(
            lambda: aggregate_with_polars(
                file_path,
                lower_bound,
                upper_bound,
            ),
            number=BENCHMARK_NUMBER,
        )

        duckdb_time = timeit.timeit(
            lambda: aggregate_with_duckdb(
                file_path,
                lower_bound,
                upper_bound,
            ),
            number=BENCHMARK_NUMBER,
        )

    except Exception as error:
        raise RuntimeError(
            f"성능 측정 중 오류가 발생했습니다: {error}"
        ) from error

    return {
        "Pandas": pandas_time,
        "Polars": polars_time,
        "DuckDB": duckdb_time,
    }

# --------------------------------------------------
# 8. 프로그램 전체 실행
# --------------------------------------------------

def main() -> None:
    """
    데이터 검증부터 세 도구의 집계 및 성능 비교까지 순서대로 실행한다.
    """
    df = load_sales_data(FILE_PATH)

    print("\n[Pandas 기본 정보]")
    df.info()

    print("\n[컬럼별 결측치 개수]")
    print(df.isnull().sum())

    df_clean, lower_bound, upper_bound = remove_amount_outliers(df)

    pandas_summary = aggregate_with_pandas(df_clean)
    print("\n[Pandas named aggregation 결과]")
    print(pandas_summary)

    polars_summary = aggregate_with_polars(
        FILE_PATH,
        lower_bound,
        upper_bound,
    )
    print("\n[Polars Lazy API 결과]")
    print(polars_summary)

    duckdb_summary = aggregate_with_duckdb(
        FILE_PATH,
        lower_bound,
        upper_bound,
    )
    print("\n[DuckDB SQL 결과]")
    print(duckdb_summary)

    # 결과가 일치할 때만 성능을 비교한다.
    validate_results(
        pandas_summary,
        polars_summary,
        duckdb_summary,
    )

    benchmark_result = benchmark_tools(
        FILE_PATH,
        lower_bound,
        upper_bound,
    )

    print(f"\n[성능 비교 결과 - 각 {BENCHMARK_NUMBER}회 실행]")

    for tool, total_time in benchmark_result.items():
        average_time = total_time / BENCHMARK_NUMBER

        print(
            f"{tool:<7}: "
            f"전체 {total_time:.4f}초 / "
            f"평균 {average_time:.4f}초"
        )


if __name__ == "__main__":
    try:
        main()

    except (
        FileNotFoundError,
        PermissionError,
        ValueError,
        RuntimeError,
    ) as error:
        print(f"\n[프로그램 오류] {error}")

    except Exception as error:
        print(
            f"\n[예상하지 못한 오류] "
            f"{type(error).__name__}: {error}"
        )
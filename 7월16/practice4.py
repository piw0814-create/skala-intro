"""
Python Practice 4 - 판매 데이터 통계 분석 및 머신러닝 Pipeline

작성자: 4반 박인우

프로그램 설명:
practice3.py에서 생성한 정제 데이터와 지역·카테고리별 집계 결과를
활용하여 EDA 시각화, 통계 검정, 머신러닝 Pipeline 학습을 수행한다.

주요 기능:
1. 2×2 서브플롯 EDA 시각화
2. 서울과 부산의 평균 매출 t-test
3. 지역과 카테고리의 카이제곱 독립성 검정
4. sklearn Pipeline 학습·예측·평가
5. 학습된 Pipeline 저장 및 재로딩
6. Plotly 인터랙티브 차트 HTML 저장

실습3 연계 파일:
- clean_sales.csv
- region_category_summary.csv

생성 파일:
- sales_pipeline.joblib
- region_category_sales.html

변경 내역:
- 실습3 산출물을 실습4 입력 데이터로 연계
- 통계 검정 및 p-value 해석 추가
- 전처리와 모델을 Pipeline으로 통합
- 모델과 Plotly 차트 저장 기능 추가
"""

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
from scipy import stats
from scipy.stats import chi2_contingency
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer

# --------------------------------------------------
# 공통 설정
# --------------------------------------------------

CLEAN_DATA_PATH = Path("clean_sales.csv")
SUMMARY_DATA_PATH = Path("region_category_summary.csv")

MODEL_PATH = Path("sales_pipeline.joblib")
PLOTLY_HTML_PATH = Path("region_category_sales.html")

SIGNIFICANCE_LEVEL = 0.05
RANDOM_STATE = 42

# --------------------------------------------------
# CSV 파일 로드 및 검증
# --------------------------------------------------

def load_csv(
    file_path: Path,
    required_columns: set[str],
) -> pd.DataFrame:
    """
    CSV 파일을 불러오고 필수 컬럼 존재 여부를 확인한다.

    Args:
        file_path: 불러올 CSV 파일 경로
        required_columns: 반드시 포함되어야 하는 컬럼 집합

    Returns:
        검증이 완료된 DataFrame
    """
    try:
        df = pd.read_csv(file_path)

    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {file_path}"
        ) from error

    except pd.errors.EmptyDataError as error:
        raise ValueError(
            f"파일이 비어 있습니다: {file_path}"
        ) from error

    except pd.errors.ParserError as error:
        raise ValueError(
            f"CSV 형식을 읽을 수 없습니다: {file_path}"
        ) from error

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"{file_path}에 필요한 컬럼이 없습니다: "
            f"{sorted(missing_columns)}"
        )

    if df.empty:
        raise ValueError(
            f"데이터가 존재하지 않습니다: {file_path}"
        )

    print(f"[파일 로드 완료] {file_path}: {len(df):,}행")

    return df

# --------------------------------------------------
# 2×2 EDA 시각화
# --------------------------------------------------

def create_eda_plots(df: pd.DataFrame) -> None:
    """
    정제된 판매 데이터로 4종 EDA 차트를 하나의 Figure에 출력한다.

    차트:
        1. 거래금액 히스토그램 + KDE
        2. 거래금액 박스플롯
        3. 월별 총매출 라인 차트
        4. 수치형 변수 상관 히트맵
    """
    plot_df = df.copy()

    # 월별 분석용 컬럼 생성
    if "month" in plot_df.columns:
        plot_df["sales_month"] = plot_df["month"]

    elif "order_date" in plot_df.columns:
        plot_df["order_date"] = pd.to_datetime(
            plot_df["order_date"],
            errors="coerce",
        )

        plot_df = plot_df.dropna(subset=["order_date"])

        plot_df["sales_month"] = (
            plot_df["order_date"]
            .dt.to_period("M")
            .astype(str)
        )

    else:
        raise ValueError(
            "월별 분석에 필요한 month 또는 order_date 컬럼이 없습니다."
        )

    monthly_sales = (
        plot_df.groupby("sales_month")["amount"]
        .sum()
        .sort_index()
    )

    numeric_df = (
        plot_df.select_dtypes(include="number")
        .drop(columns=["order_id"], errors="ignore")
    )

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(14, 10),
    )

    # 1. 히스토그램 + KDE
    sns.histplot(
        data=plot_df,
        x="amount",
        kde=True,
        ax=axes[0, 0],
    )
    axes[0, 0].set_title("Amount Distribution")

    # 2. 박스플롯
    sns.boxplot(
        data=plot_df,
        y="amount",
        ax=axes[0, 1],
    )
    axes[0, 1].set_title("Amount Box Plot")

    # 3. 월별 총매출 라인 차트
    axes[1, 0].plot(
        monthly_sales.index,
        monthly_sales.values,
        marker="o",
    )
    axes[1, 0].set_title("Monthly Total Sales")
    axes[1, 0].set_xlabel("Month")
    axes[1, 0].set_ylabel("Total Sales")
    axes[1, 0].tick_params(axis="x", rotation=45)

    # 4. 상관 히트맵
    sns.heatmap(
        numeric_df.corr(),
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        ax=axes[1, 1],
    )
    axes[1, 1].set_title("Correlation Heatmap")

    fig.suptitle(
        "Sales Data EDA",
        fontsize=16,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()

# --------------------------------------------------
# 서울 vs 부산 평균 매출 t-test
# --------------------------------------------------

def run_t_test(df: pd.DataFrame) -> tuple[float, float]:
    """
    서울과 부산의 평균 거래금액 차이를 Welch t-test로 검정한다.

    Args:
        df: IQR 이상치가 제거된 판매 데이터

    Returns:
        t 통계량과 p-value
    """
    seoul_amount = (
        df.loc[df["region"] == "서울", "amount"]
        .dropna()
    )

    busan_amount = (
        df.loc[df["region"] == "부산", "amount"]
        .dropna()
    )

    if len(seoul_amount) < 2 or len(busan_amount) < 2:
        raise ValueError(
            "서울과 부산의 t-test를 위한 표본이 부족합니다."
        )

    t_stat, p_value = stats.ttest_ind(
        seoul_amount,
        busan_amount,
        equal_var=False,
    )

    print("\n[t-test: 서울 vs 부산 평균 매출]")
    print(f"서울 평균: {seoul_amount.mean():,.2f}")
    print(f"부산 평균: {busan_amount.mean():,.2f}")
    print(f"t 통계량: {t_stat:.4f}")
    print(f"p-value: {p_value:.4f}")

    if p_value < SIGNIFICANCE_LEVEL:
        print(
            "해석: 서울과 부산의 평균 매출에 "
            "통계적으로 유의한 차이가 있습니다."
        )
    else:
        print(
            "해석: 서울과 부산의 평균 매출에서 "
            "통계적으로 유의한 차이를 확인하지 못했습니다."
        )

    return float(t_stat), float(p_value)

# --------------------------------------------------
# 지역 × 카테고리 카이제곱 검정
# --------------------------------------------------

def run_chi_square_test(
    summary_df: pd.DataFrame,
) -> tuple[float, float]:
    """
    지역과 카테고리의 독립성을 카이제곱 검정으로 확인한다.

    Args:
        summary_df: region·category별 집계 결과

    Returns:
        카이제곱 통계량과 p-value
    """
    test_df = summary_df.copy()

    test_df["count"] = pd.to_numeric(
        test_df["count"],
        errors="coerce",
    )

    test_df = test_df.dropna(
        subset=["region", "category", "count"],
    )

    contingency_table = test_df.pivot_table(
        index="region",
        columns="category",
        values="count", 
        aggfunc="sum",
        fill_value=0,
    )

    if contingency_table.shape[0] < 2:
        raise ValueError(
            "카이제곱 검정에는 지역이 2개 이상 필요합니다."
        )

    if contingency_table.shape[1] < 2:
        raise ValueError(
            "카이제곱 검정에는 카테고리가 2개 이상 필요합니다."
        )

    chi2, p_value, dof, expected = chi2_contingency(
        contingency_table
    )

    print("\n[카이제곱 검정: 지역 × 카테고리]")
    print(contingency_table)
    print(f"카이제곱 통계량: {chi2:.4f}")
    print(f"자유도: {dof}")
    print(f"p-value: {p_value:.4f}")

    if p_value < SIGNIFICANCE_LEVEL:
        print(
            "해석: 지역과 카테고리는 독립이 아니며 "
            "통계적으로 유의한 관련성이 있습니다."
        )
    else:
        print(
            "해석: 지역과 카테고리 사이에서 "
            "통계적으로 유의한 관련성을 확인하지 못했습니다."
        )

    if (expected < 5).any():
        print(
            "주의: 기대빈도가 5 미만인 셀이 있어 "
            "검정 결과 해석에 주의가 필요합니다."
        )

    return float(chi2), float(p_value)

# --------------------------------------------------
# sklearn Pipeline 학습 및 평가
# --------------------------------------------------

def build_and_train_pipeline(
    clean_df: pd.DataFrame,
) -> tuple[Pipeline, pd.DataFrame, pd.Series]:
    """
    IQR 이상치가 제거된 판매 데이터로 amount 예측 Pipeline을 학습한다.

    Args:
        clean_df: practice3.py에서 생성한 clean_sales.csv 데이터

    Returns:
        학습된 Pipeline, 테스트 입력값, 테스트 정답
    """
    model_df = clean_df.copy()

    model_df["amount"] = pd.to_numeric(
        model_df["amount"],
        errors="coerce",
    )
    model_df = model_df.dropna(subset=["amount"])

    excluded_columns = [
        column
        for column in ["amount", "order_id", "order_date"]
        if column in model_df.columns
    ]

    X = model_df.drop(columns=excluded_columns)
    y = model_df["amount"]

    numeric_columns = (
        X.select_dtypes(include="number")
        .columns
        .tolist()
    )

    categorical_columns = (
        X.select_dtypes(
            include=["object", "str", "category", "bool"]
        )
        .columns
        .tolist()
    )

    if not numeric_columns and not categorical_columns:
        raise ValueError(
            "Pipeline 학습에 사용할 입력 컬럼이 없습니다."
        )

    # 지원하지 않는 자료형 컬럼 제외
    X = X[numeric_columns + categorical_columns]

    numeric_pipeline = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
        (
            "scaler",
            StandardScaler(),
        ),
    ])

    categorical_pipeline = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="most_frequent"),
        ),
        (
            "encoder",
            OneHotEncoder(handle_unknown="ignore"),
        ),
    ])

    transformers = []

    if numeric_columns:
        transformers.append(
            ("num", numeric_pipeline, numeric_columns)
        )

    if categorical_columns:
        transformers.append(
            ("cat", categorical_pipeline, categorical_columns)
        )

    preprocessor = ColumnTransformer(
        transformers=transformers
    )

    model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", Ridge(alpha=1.0)),
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    score = model.score(X_test, y_test)

    print("\n[sklearn Pipeline 평가]")
    print(f"훈련 데이터: {len(X_train):,}건")
    print(f"테스트 데이터: {len(X_test):,}건")
    print(f"R² 점수: {score:.4f}")
    print(f"예측값 예시: {predictions[:5]}")

    return model, X_test, y_test

# --------------------------------------------------
# Pipeline 저장 및 재로딩
# --------------------------------------------------

def save_and_reload_model(
    model: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Pipeline:
    """
    학습된 Pipeline을 파일로 저장하고 다시 불러와 정상 작동을 확인한다.

    Args:
        model: 학습이 완료된 Pipeline
        X_test: 테스트 입력 데이터
        y_test: 테스트 정답 데이터

    Returns:
        파일에서 다시 불러온 Pipeline
    """
    try:
        joblib.dump(model, MODEL_PATH)
        loaded_model = joblib.load(MODEL_PATH)

    except OSError as error:
        raise RuntimeError(
            f"모델 저장 또는 로딩에 실패했습니다: {error}"
        ) from error

    loaded_predictions = loaded_model.predict(X_test)
    loaded_score = loaded_model.score(X_test, y_test)

    print("\n[Pipeline 저장 및 재로딩]")
    print(f"모델 저장 완료: {MODEL_PATH.resolve()}")
    print(f"재로딩 모델 R²: {loaded_score:.4f}")
    print(f"재로딩 예측값 예시: {loaded_predictions[:5]}")

    return loaded_model

# --------------------------------------------------
# Plotly 차트 생성 및 HTML 저장
# --------------------------------------------------

def create_plotly_chart(
    summary_df: pd.DataFrame,
) -> None:
    """
    지역·카테고리별 총매출을 Plotly 막대 차트로 만들고 HTML로 저장한다.

    Args:
        summary_df: region·category별 집계 결과
    """
    chart_df = summary_df.copy()

    chart_df["total"] = pd.to_numeric(
        chart_df["total"],
        errors="coerce",
    )

    chart_df = chart_df.dropna(
        subset=["region", "category", "total"],
    )

    if chart_df.empty:
        raise ValueError(
            "Plotly 차트에 사용할 데이터가 없습니다."
        )

    fig = px.bar(
        chart_df,
        x="region",
        y="total",
        color="category",
        barmode="group",
        title="지역·카테고리별 총매출",
        labels={
            "region": "지역",
            "total": "총매출",
            "category": "카테고리",
        },
    )

    try:
        fig.write_html(PLOTLY_HTML_PATH)

    except OSError as error:
        raise RuntimeError(
            f"Plotly HTML 저장에 실패했습니다: {error}"
        ) from error

    print("\n[Plotly 차트 저장]")
    print(f"HTML 저장 완료: {PLOTLY_HTML_PATH.resolve()}")

# --------------------------------------------------
# 메인 실행 함수
# --------------------------------------------------

def main() -> None:
    """
    실습3 산출물을 불러온 후 EDA, 통계 검정,
    Pipeline 학습·저장 및 Plotly 차트 생성을 순서대로 수행한다.
    """
    print("=" * 60)
    print("Python Practice 4 실행")
    print("=" * 60)

    # 실습3 산출물 로드
    clean_df = load_csv(
        CLEAN_DATA_PATH,
        {"region", "category", "amount"},
    )

    summary_df = load_csv(
        SUMMARY_DATA_PATH,
        {"region", "category", "total", "count"},
    )

    # 1. 2×2 EDA 시각화
    create_eda_plots(clean_df)

    # 2. 통계 검정
    run_t_test(clean_df)
    run_chi_square_test(summary_df)

    # 3. Pipeline 학습·예측·평가
    model, X_test, y_test = build_and_train_pipeline(
        clean_df
    )

    # 4. Pipeline 저장 및 재로딩
    save_and_reload_model(
        model,
        X_test,
        y_test,
    )

    # 5. Plotly 차트 HTML 저장
    create_plotly_chart(summary_df)

    print("\n" + "=" * 60)
    print("모든 작업이 정상적으로 완료되었습니다.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()

    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
    ) as error:
        print(f"\n[실행 오류] {error}")

    except Exception as error:
        print(
            "\n[예상하지 못한 오류] "
            f"{type(error).__name__}: {error}"
        )


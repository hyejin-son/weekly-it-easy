"""
WeeklyReportCalculator 단위 테스트 (Task 1-1 + Task 1-2)

Mock Excel 데이터를 메모리에서 생성하여 로직 1~5를 검증한다.

테스트 케이스 목록:
    [로직 1] 파일 통합
        test_01_consolidate_ab_files        - AB 2개 concat 행 수 확인
        test_02_consolidate_cd_files        - CD 2개 concat 행 수 확인

    [로직 2] 필터링
        test_03_epro_filter_f_column        - F열 e-Procurement → 포함
        test_04_epro_filter_w_column        - W열 e-Procurement → 포함 (OR 조건)
        test_05_epro_filter_excludes_others - F/W 모두 불일치 → 제외
        test_06_date_filter_in_range        - 해당 주 날짜 → 포함
        test_07_date_filter_out_of_range    - 다른 주 날짜 → 제외
        test_08_empty_date_always_included  - 날짜 NaN → 항상 포함
        test_09_t_column_branches_to_z      - T열 있으면 Z열 기준으로 날짜 필터

    [로직 3] 기본 매핑
        test_10_status_mapping              - B열 → '완료'/'대기'/'진행중'
        test_11_schedule_p_over_o           - P열 우선, 없으면 O열 → ~MM/DD
        test_12_category_no_t_uses_c        - T열 NaN → C열 그대로
        test_13_category_with_t_cd_lookup   - T열 있음 → CD join → D열 분기

    [로직 4] 텍스트 추출
        test_14_text_extraction_branching   - T없음+P있음/없음, T있음+Z있음/없음

    [로직 5] Gemini 윤문 (Task 1-2)
        test_15_gemini_refines_records          - 정상 응답 → refined 필드 반영
        test_16_gemini_fallback_on_all_failures - 3회 모두 실패 → original 유지
        test_17_gemini_retry_then_succeed       - 1회 실패 후 성공 → refined 필드 반영
        test_18_gemini_invalid_json_fallback    - 잘못된 JSON → original 유지
        test_19_gemini_skipped_when_no_api_key  - API 키 없을 때 → refined 필드 None
        test_20_gemini_empty_records_no_call    - 빈 레코드 → API 호출 없음
"""

import io
import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import openpyxl
import pandas as pd
import pytest

from server.app.domain.weekly_report.calculator import (
    COL_AB,
    COL_A,
    COL_B,
    COL_C,
    COL_D,
    COL_F,
    COL_G,
    COL_H,
    COL_J,
    COL_O,
    COL_P,
    COL_R,
    COL_T,
    COL_W,
    COL_Z,
    MIN_REQUIRED_COLS,
    CATEGORY_DEV,
    CATEGORY_DEV_VALUE,
    CATEGORY_OPS,
    EPRO_VALUES,
    WeeklyReportCalculator,
    WeeklyReportCalculatorInput,
)

# ====================
# 상수
# ====================

EPRO_BESTEEL = "세아베스틸>기타>e-Procurement"
EPRO_CHANGWON = "세아창원특수강>기타>e-Procurement"
NON_EPRO = "기타시스템"

# 테스트용 기준 날짜: 2026-03-06 (금요일)
# → 해당 주 월요일 = 2026-03-02, 금요일 = 2026-03-06
REPORT_DATE = "2026-03-06"
IN_RANGE_DATE = "2026-03-04"   # 수요일 (범위 내)
OUT_OF_RANGE_DATE = "2026-03-10"  # 다음 주 화요일 (범위 외)


# ====================
# Mock Excel 헬퍼
# ====================


def make_excel_bytes(data_rows: list[list], n_cols: int = MIN_REQUIRED_COLS) -> bytes:
    """
    3개의 헤더 행(row1 = sentinel, row2 = 더미, row3 = 빈 헤더) +
    데이터 행으로 구성된 Excel bytes를 메모리에서 생성한다.

    pd.read_excel(header=2) 호출 시 row3이 헤더로 읽힌다.
    컬럼이 n_cols개 미만인 행은 None으로 패딩한다.

    주의: row1에 sentinel 문자열을 넣는 이유 —
      openpyxl은 trailing None 셀을 파일에 기록하지 않는다.
      이로 인해 pandas가 실제 컬럼 수보다 적은 수의 컬럼을 읽는 문제가 발생한다.
      row1에 n_cols개의 비-None 값을 넣어 Excel 파일의 컬럼 범위를 강제로 확정한다.
    """
    wb = openpyxl.Workbook()
    ws = wb.active

    # row 1, 2, 3: 모두 non-empty 값으로 채워야 pandas TextParser가 건너뛰지 않음
    # (pandas는 skip_blank_lines=True가 기본이므로 all-empty 행을 건너뜀)
    # → header=2 요청 시 텍스트 파서가 line_pos=2에 도달하지 못해 StopIteration 발생
    ws.append([f"_r0c{i}" for i in range(n_cols)])  # row 1 (더미; 행 존재 보장)
    ws.append([f"_r1c{i}" for i in range(n_cols)])  # row 2 (더미; 행 존재 보장)
    ws.append([f"_r2c{i}" for i in range(n_cols)])  # row 3 (헤더; 컬럼명 _r2c0.._r2c27)

    for row in data_rows:
        padded = list(row) + [None] * (n_cols - len(row))
        ws.append(padded)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_empty_excel_bytes(n_cols: int = MIN_REQUIRED_COLS) -> bytes:
    """데이터 행이 없는 빈 Excel bytes를 생성한다."""
    return make_excel_bytes([], n_cols=n_cols)


def build_row(overrides: dict[int, object], n_cols: int = MIN_REQUIRED_COLS) -> list:
    """
    n_cols 크기의 None 리스트를 만들고 overrides dict로 특정 인덱스 값을 설정한다.

    사용 예:
        row = build_row({COL_A: "REQ-001", COL_B: "종료", COL_F: EPRO_BESTEEL})
    """
    row = [None] * n_cols
    for idx, val in overrides.items():
        row[idx] = val
    return row


def make_calculator_input(
    ab1_rows: list[list],
    ab2_rows: list[list],
    cd1_rows: list[list] | None = None,
    cd2_rows: list[list] | None = None,
    report_date: str = REPORT_DATE,
) -> WeeklyReportCalculatorInput:
    """WeeklyReportCalculatorInput을 간편하게 생성하는 팩토리 함수."""
    return WeeklyReportCalculatorInput(
        report_date=report_date,
        file_ab_1=make_excel_bytes(ab1_rows),
        file_ab_2=make_excel_bytes(ab2_rows),
        file_cd_1=make_excel_bytes(cd1_rows or []),
        file_cd_2=make_excel_bytes(cd2_rows or []),
    )


# ====================
# Fixture
# ====================


@pytest.fixture
def calculator() -> WeeklyReportCalculator:
    return WeeklyReportCalculator()


def epro_row(overrides: dict | None = None) -> list:
    """e-Procurement 값이 F열에 설정된 기본 행을 반환한다.

    Args:
        overrides: 컬럼 인덱스(정수) → 값 dict. 기본값을 덮어쓴다.
    """
    base = {
        COL_A: "REQ-001",
        COL_B: "진행",
        COL_C: "운영",
        COL_F: EPRO_BESTEEL,
        COL_G: "제목 텍스트",
        COL_H: "요구사항 텍스트",
        COL_J: "창원",
    }
    if overrides:
        base.update(overrides)
    return build_row(base)


# ====================
# 로직 1: 파일 통합
# ====================


@pytest.mark.asyncio
async def test_01_consolidate_ab_files(calculator):
    """AB 파일 2개를 concat하면 행 수가 합산된다."""
    ab1_rows = [epro_row({COL_A: "R1"}), epro_row({COL_A: "R2"})]
    ab2_rows = [epro_row({COL_A: "R3"})]
    inp = make_calculator_input(ab1_rows, ab2_rows)

    df_ab, _ = calculator._consolidate_files(inp)

    assert len(df_ab) == 3, f"AB concat 결과 행 수가 3이어야 함, 실제: {len(df_ab)}"


@pytest.mark.asyncio
async def test_02_consolidate_cd_files(calculator):
    """CD 파일 2개를 concat하면 행 수가 합산된다."""
    cd1_rows = [build_row({COL_A: "R1", COL_D: CATEGORY_DEV_VALUE})]
    cd2_rows = [
        build_row({COL_A: "R2", COL_D: CATEGORY_DEV_VALUE}),
        build_row({COL_A: "R3", COL_D: "기타"}),
    ]
    inp = make_calculator_input([], [], cd1_rows, cd2_rows)

    _, df_cd = calculator._consolidate_files(inp)

    assert len(df_cd) == 3, f"CD concat 결과 행 수가 3이어야 함, 실제: {len(df_cd)}"


# ====================
# 로직 2: 필터링
# ====================


@pytest.mark.asyncio
async def test_03_epro_filter_f_column(calculator):
    """F열이 e-Procurement 값이면 필터링에 포함된다."""
    row = build_row({
        COL_F: EPRO_BESTEEL,
        COL_P: IN_RANGE_DATE,
    })
    inp = make_calculator_input([row], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 1


@pytest.mark.asyncio
async def test_04_epro_filter_w_column(calculator):
    """W열이 e-Procurement 값이면 F열에 값이 없어도 포함된다 (OR 조건)."""
    row = build_row({
        COL_F: NON_EPRO,
        COL_W: EPRO_CHANGWON,
        COL_P: IN_RANGE_DATE,
    })
    inp = make_calculator_input([row], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 1


@pytest.mark.asyncio
async def test_05_epro_filter_excludes_others(calculator):
    """F열, W열 모두 e-Procurement 값이 아니면 제외된다."""
    row = build_row({
        COL_F: NON_EPRO,
        COL_W: NON_EPRO,
        COL_P: IN_RANGE_DATE,
    })
    inp = make_calculator_input([row], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 0


@pytest.mark.asyncio
async def test_06_date_filter_in_range(calculator):
    """해당 주 날짜(P열)가 있으면 포함된다."""
    row = build_row({
        COL_F: EPRO_BESTEEL,
        COL_P: IN_RANGE_DATE,  # 2026-03-04 (해당 주)
    })
    inp = make_calculator_input([row], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 1


@pytest.mark.asyncio
async def test_07_date_filter_out_of_range(calculator):
    """다른 주 날짜(P열)가 있으면 제외된다."""
    row = build_row({
        COL_F: EPRO_BESTEEL,
        COL_P: OUT_OF_RANGE_DATE,  # 2026-03-10 (다음 주)
    })
    inp = make_calculator_input([row], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 0


@pytest.mark.asyncio
async def test_08_empty_date_always_included(calculator):
    """P열, Z열 모두 NaN이면 날짜 무관하게 항상 포함된다 (진행중/대기 건)."""
    row = build_row({
        COL_F: EPRO_BESTEEL,
        # COL_P, COL_Z 없음 (NaN)
    })
    inp = make_calculator_input([row], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 1


@pytest.mark.asyncio
async def test_09_t_column_branches_to_z(calculator):
    """T열이 있으면 P열이 아닌 Z열을 날짜 기준으로 사용한다."""
    # P열에는 범위 밖 날짜, Z열에는 범위 내 날짜
    # T열이 있으므로 Z열 기준 → 포함되어야 함
    row_included = build_row({
        COL_F: EPRO_BESTEEL,
        COL_T: "CHG-001",          # T열 있음
        COL_P: OUT_OF_RANGE_DATE,  # 무시되어야 할 P열
        COL_Z: IN_RANGE_DATE,      # 실제 기준 Z열
    })
    # T열이 있고 Z열이 범위 밖 → 제외되어야 함
    row_excluded = build_row({
        COL_F: EPRO_BESTEEL,
        COL_T: "CHG-002",          # T열 있음
        COL_P: IN_RANGE_DATE,      # 무시되어야 할 P열
        COL_Z: OUT_OF_RANGE_DATE,  # 실제 기준 Z열
    })
    inp = make_calculator_input([row_included, row_excluded], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 1
    assert result.records[0].request_id == ""  # A열 미설정이므로 빈 문자열


# ====================
# 로직 3: 기본 매핑
# ====================


@pytest.mark.asyncio
async def test_10_status_mapping(calculator):
    """B열 값에 따라 '완료'/'대기'/'진행중'으로 올바르게 매핑된다."""
    cases = [
        ("종료", "완료"),
        ("중단종료", "완료"),
        ("취소종료", "완료"),
        ("요청 접수 및 분류", "대기"),
        ("검토중", "진행중"),
        ("개발중", "진행중"),
    ]

    rows = [
        build_row({COL_F: EPRO_BESTEEL, COL_A: f"R{i}", COL_B: b_val})
        for i, (b_val, _) in enumerate(cases)
    ]
    inp = make_calculator_input(rows, [])
    result = await calculator.calculate(inp)

    assert len(result.records) == len(cases)
    for record, (_, expected_status) in zip(result.records, cases):
        assert record.status == expected_status, (
            f"B열='{record}' → status='{record.status}', 기대: '{expected_status}'"
        )


@pytest.mark.asyncio
async def test_11_schedule_p_over_o(calculator):
    """P열이 있으면 P열을 사용하고, 없으면 O열을 사용한다. 형식은 ~MM/DD."""
    # row_p: P열(해당 주 날짜)과 O열 모두 있음 → P열 우선, schedule = ~03/04
    # row_o: P열 없음 + O열만 있음 → O열 사용, schedule = ~04/10
    # row_none: P, O 둘 다 없음 → None
    # ※ date filter 기준: T없음 → P열. P=None이면 항상 포함(진행중 건)
    row_p = build_row({COL_F: EPRO_BESTEEL, COL_A: "R1", COL_P: IN_RANGE_DATE, COL_O: OUT_OF_RANGE_DATE})
    row_o = build_row({COL_F: EPRO_BESTEEL, COL_A: "R2", COL_P: None,           COL_O: "2026-04-10"})
    row_none = build_row({COL_F: EPRO_BESTEEL, COL_A: "R3"})  # 둘 다 없음

    inp = make_calculator_input([row_p, row_o, row_none], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 3
    assert result.records[0].schedule == f"~{IN_RANGE_DATE[5:7]}/{IN_RANGE_DATE[8:10]}", "P열 우선 사용"
    assert result.records[1].schedule == "~04/10", "P열 없으면 O열 사용"
    assert result.records[2].schedule is None,     "P/O 모두 없으면 None"


@pytest.mark.asyncio
async def test_12_category_no_t_uses_c(calculator):
    """T열이 NaN이면 C열 값을 그대로 구분으로 사용한다."""
    row = build_row({
        COL_F: EPRO_BESTEEL,
        COL_C: "운영지원",
        # COL_T: None → NaN
    })
    inp = make_calculator_input([row], [])
    result = await calculator.calculate(inp)

    assert result.records[0].category == "운영지원"


@pytest.mark.asyncio
async def test_13_category_with_t_cd_lookup(calculator):
    """T열이 있으면 CD 파일에서 A열로 join 후 D열 값에 따라 구분을 결정한다."""
    # CD 파일에 REQ-DEV → 개발/개선, REQ-OPS → 프로젝트/운영
    cd_rows = [
        build_row({COL_A: "REQ-DEV", COL_D: CATEGORY_DEV_VALUE}),
        build_row({COL_A: "REQ-OPS", COL_D: "기타업무"}),
    ]

    row_dev = build_row({
        COL_F: EPRO_BESTEEL,
        COL_A: "REQ-DEV",
        COL_T: "CHG-001",  # T열 있음
    })
    row_ops = build_row({
        COL_F: EPRO_BESTEEL,
        COL_A: "REQ-OPS",
        COL_T: "CHG-002",  # T열 있음
    })
    row_missing = build_row({
        COL_F: EPRO_BESTEEL,
        COL_A: "REQ-UNKNOWN",  # CD에 없는 ID
        COL_T: "CHG-003",
    })

    inp = make_calculator_input([row_dev, row_ops, row_missing], [], cd_rows, [])
    result = await calculator.calculate(inp)

    assert result.records[0].category == CATEGORY_DEV, "개발/개선 분류"
    assert result.records[1].category == CATEGORY_OPS, "프로젝트/운영 분류"
    assert result.records[2].category == CATEGORY_OPS, "CD 미발견 → 프로젝트/운영"


# ====================
# 로직 4: 텍스트 추출
# ====================


@pytest.mark.asyncio
async def test_14_text_extraction_branching(calculator):
    """
    T열 유무 × P/Z열 유무 4가지 분기에 따라 텍스트가 올바르게 추출된다.

    케이스 1: T없음 + P있음 → processing_content = R열
    케이스 2: T없음 + P없음 → processing_content = None
    케이스 3: T있음 + Z있음 → processing_content = AB열
    케이스 4: T있음 + Z없음 → processing_content = None
    """
    # 케이스 1: T없음 + P있음 → R열
    row1 = build_row({
        COL_F: EPRO_BESTEEL, COL_A: "R1",
        COL_G: "제목1", COL_H: "요구1",
        COL_P: IN_RANGE_DATE, COL_R: "처리내용-R",
    })
    # 케이스 2: T없음 + P없음 → processing_content = None
    row2 = build_row({
        COL_F: EPRO_BESTEEL, COL_A: "R2",
        COL_G: "제목2", COL_H: "요구2",
        COL_R: "처리내용-R-무시",  # P열 없으면 R열도 무시
    })
    # 케이스 3: T있음 + Z있음 → AB열
    row3 = build_row({
        COL_F: EPRO_BESTEEL, COL_A: "R3",
        COL_G: "제목3", COL_H: "요구3",
        COL_T: "CHG-003", COL_Z: IN_RANGE_DATE, COL_AB: "처리내용-AB",
    })
    # 케이스 4: T있음 + Z없음 → processing_content = None
    row4 = build_row({
        COL_F: EPRO_BESTEEL, COL_A: "R4",
        COL_G: "제목4", COL_H: "요구4",
        COL_T: "CHG-004",
        COL_AB: "처리내용-AB-무시",  # Z열 없으면 AB열도 무시
    })

    inp = make_calculator_input([row1, row2, row3, row4], [])
    result = await calculator.calculate(inp)

    assert len(result.records) == 4

    r1 = result.records[0]
    assert r1.title == "제목1"
    assert r1.requirements == "요구1"
    assert r1.processing_content == "처리내용-R", "케이스1: T없음+P있음 → R열"

    r2 = result.records[1]
    assert r2.title == "제목2"
    assert r2.processing_content is None, "케이스2: T없음+P없음 → None"

    r3 = result.records[2]
    assert r3.title == "제목3"
    assert r3.processing_content == "처리내용-AB", "케이스3: T있음+Z있음 → AB열"

    r4 = result.records[3]
    assert r4.title == "제목4"
    assert r4.processing_content is None, "케이스4: T있음+Z없음 → None"


# ====================
# 경계 케이스 / 추가 검증
# ====================


@pytest.mark.asyncio
async def test_invalid_report_date_raises(calculator):
    """잘못된 날짜 형식이면 ValueError가 발생한다."""
    # Python 3.11+에서 "YYYYMMDD"는 fromisoformat이 지원하므로, 확실히 잘못된 형식 사용
    inp = make_calculator_input([], [], report_date="2026/03/06")  # 슬래시는 ISO 형식 아님
    with pytest.raises(ValueError, match="report_date"):
        await calculator.calculate(inp)


@pytest.mark.asyncio
async def test_insufficient_columns_raises(calculator):
    """컬럼 수가 28개 미만이면 ValueError가 발생한다."""
    # n_cols=10으로 작은 Excel 생성
    small_bytes = make_excel_bytes([], n_cols=10)
    inp = WeeklyReportCalculatorInput(
        report_date=REPORT_DATE,
        file_ab_1=small_bytes,
        file_ab_2=small_bytes,
        file_cd_1=small_bytes,
        file_cd_2=small_bytes,
    )
    with pytest.raises(ValueError, match="컬럼 수가 부족"):
        await calculator.calculate(inp)


@pytest.mark.asyncio
async def test_empty_files_return_empty_records(calculator):
    """데이터 행이 없는 파일이면 빈 레코드 리스트를 반환한다."""
    inp = make_calculator_input([], [])
    result = await calculator.calculate(inp)

    assert result.records == []


def test_get_week_range_monday_input():
    """월요일을 입력해도 월~금 범위를 올바르게 반환한다."""
    calc = WeeklyReportCalculator()
    monday, friday = calc._get_week_range("2026-03-02")  # 실제 월요일
    assert monday == date(2026, 3, 2)
    assert friday == date(2026, 3, 6)


def test_get_week_range_friday_input():
    """금요일을 입력해도 동일한 주의 월~금 범위를 반환한다."""
    calc = WeeklyReportCalculator()
    monday, friday = calc._get_week_range("2026-03-06")  # 금요일
    assert monday == date(2026, 3, 2)
    assert friday == date(2026, 3, 6)


# ====================
# 로직 5: Gemini 윤문 (Task 1-2)
# ====================

# Gemini 배치 응답 JSON 샘플 (test_15, test_17에서 공통 사용)
GEMINI_BATCH_RESPONSE = json.dumps(
    [
        {
            "id": 0,
            "refined_title": "윤문된 제목",
            "refined_overview": "윤문된 개요",
            "refined_content": "윤문된 내용",
        }
    ],
    ensure_ascii=False,
)


def _make_calculator_with_mock_model(mock_model) -> WeeklyReportCalculator:
    """Mock Gemini 모델이 주입된 WeeklyReportCalculator를 반환한다."""
    calc = WeeklyReportCalculator.__new__(WeeklyReportCalculator)
    calc._gemini_model = mock_model
    return calc


@pytest.mark.asyncio
async def test_15_gemini_refines_records():
    """Gemini 정상 응답 시 refined 필드 3개가 레코드에 반영된다."""
    mock_response = MagicMock()
    mock_response.text = GEMINI_BATCH_RESPONSE

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    calc = _make_calculator_with_mock_model(mock_model)

    row = epro_row({COL_G: "제목 원본", COL_H: "요구사항 원본", COL_P: IN_RANGE_DATE, COL_R: "처리 원본"})
    inp = make_calculator_input([row], [])

    # calculate() 호출 시 _init_gemini는 이미 Mock으로 대체됐으므로 직접 호출
    result = await calc.calculate(inp)

    assert len(result.records) == 1
    r = result.records[0]
    assert r.refined_title == "윤문된 제목", "refined_title이 반영되어야 함"
    assert r.refined_overview == "윤문된 개요", "refined_overview가 반영되어야 함"
    assert r.refined_content == "윤문된 내용", "refined_content가 반영되어야 함"
    # 원본 필드는 유지
    assert r.title == "제목 원본"
    assert r.requirements == "요구사항 원본"


@pytest.mark.asyncio
async def test_16_gemini_fallback_on_all_failures():
    """Gemini API가 3회 모두 실패하면 원본 텍스트를 유지하고 refined 필드는 None이다."""
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(
        side_effect=Exception("API 오류")
    )

    calc = _make_calculator_with_mock_model(mock_model)

    row = epro_row({COL_G: "원본 제목", COL_H: "원본 요구사항"})
    inp = make_calculator_input([row], [])

    # asyncio.sleep을 mock으로 대체하여 테스트 속도 향상
    with patch("server.app.domain.weekly_report.calculator.asyncio.sleep", new_callable=AsyncMock):
        result = await calc.calculate(inp)

    assert len(result.records) == 1
    r = result.records[0]
    # refined 필드는 None (원본 유지)
    assert r.refined_title is None
    assert r.refined_overview is None
    assert r.refined_content is None
    # 원본 필드는 그대로
    assert r.title == "원본 제목"
    assert r.requirements == "원본 요구사항"
    # 3회 호출 시도 확인 (최초 1회 + 재시도 2회)
    assert mock_model.generate_content_async.call_count == 3


@pytest.mark.asyncio
async def test_17_gemini_retry_then_succeed():
    """Gemini API가 1회 실패 후 2회째에 성공하면 refined 필드가 반영된다."""
    mock_response = MagicMock()
    mock_response.text = GEMINI_BATCH_RESPONSE

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(
        side_effect=[Exception("첫 번째 실패"), mock_response]
    )

    calc = _make_calculator_with_mock_model(mock_model)

    row = epro_row({COL_P: IN_RANGE_DATE})
    inp = make_calculator_input([row], [])

    with patch("server.app.domain.weekly_report.calculator.asyncio.sleep", new_callable=AsyncMock):
        result = await calc.calculate(inp)

    assert len(result.records) == 1
    r = result.records[0]
    assert r.refined_title == "윤문된 제목", "재시도 성공 후 refined_title이 반영되어야 함"
    assert mock_model.generate_content_async.call_count == 2


@pytest.mark.asyncio
async def test_18_gemini_invalid_json_fallback():
    """Gemini 응답이 유효하지 않은 JSON이면 원본 텍스트를 유지한다."""
    mock_response = MagicMock()
    mock_response.text = "이것은 JSON이 아닙니다. { invalid json }"

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    calc = _make_calculator_with_mock_model(mock_model)

    row = epro_row({COL_G: "원본 제목", COL_H: "원본 요구사항"})
    inp = make_calculator_input([row], [])

    result = await calc.calculate(inp)

    assert len(result.records) == 1
    r = result.records[0]
    assert r.refined_title is None, "파싱 실패 시 refined_title은 None이어야 함"
    assert r.refined_overview is None
    assert r.refined_content is None
    assert r.title == "원본 제목", "원본 필드는 유지되어야 함"


@pytest.mark.asyncio
async def test_19_gemini_skipped_when_no_api_key():
    """GEMINI_API_KEY가 없으면 Gemini 모델이 None이며 윤문을 건너뛴다."""
    with patch("server.app.domain.weekly_report.calculator.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = ""
        calc = WeeklyReportCalculator()

    assert calc._gemini_model is None, "API 키 없으면 _gemini_model은 None이어야 함"

    row = epro_row({COL_G: "원본 제목", COL_H: "원본 요구사항"})
    inp = make_calculator_input([row], [])

    result = await calc.calculate(inp)

    assert len(result.records) == 1
    r = result.records[0]
    # Gemini 미사용이므로 refined 필드는 None
    assert r.refined_title is None
    assert r.refined_overview is None
    assert r.refined_content is None


@pytest.mark.asyncio
async def test_20_gemini_empty_records_no_call():
    """레코드가 없을 때 Gemini API를 호출하지 않는다."""
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock()

    calc = _make_calculator_with_mock_model(mock_model)

    # 필터링 후 레코드가 0개가 되도록 e-Procurement 미포함 행
    row = build_row({COL_F: NON_EPRO, COL_W: NON_EPRO})
    inp = make_calculator_input([row], [])

    result = await calc.calculate(inp)

    assert result.records == []
    mock_model.generate_content_async.assert_not_called()

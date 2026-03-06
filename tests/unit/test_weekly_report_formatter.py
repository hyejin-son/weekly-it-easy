"""
Task 2-1 WeeklyReportFormatter 단위 테스트

테스트 케이스:
    TC-1  데이터 없음 → 빈 문자열
    TC-2  창원만 있는 경우 → [베스틸] 섹션 없음
    TC-3  베스틸만 있는 경우 → [창원] 섹션 없음
    TC-4  두 섹션 모두 있는 경우 → 헤더·섹션·순서 확인
    TC-5  처리내용 없는 항목 → -. 내용 라인 생략
    TC-6  처리내용 있는 항목 → -. 내용 라인 포함
    TC-7  refined_* 필드 우선 사용, 없으면 원본 fallback
    TC-8  schedule=None → 일정 부분 생략
    TC-9  한 섹션에 여러 항목 → 항목 간 빈 줄
    TC-10 창원·베스틸 혼재 + 내용 없는 항목 혼재 (복합 케이스)
    TC-11 company에 '창원'/'베스틸'이 부분 문자열로 포함된 경우 분류
"""

import asyncio
from typing import Optional

import pytest

from server.app.domain.weekly_report.calculator import ProcessedRecord
from server.app.domain.weekly_report.formatter import (
    WeeklyReportFormatter,
    WeeklyReportFormatterInput,
)


# ====================
# 헬퍼
# ====================


def make_record(
    *,
    request_id: str = "REQ-001",
    status: str = "진행중",
    schedule: Optional[str] = "~03/07",
    category: str = "프로젝트/운영",
    company: str = "세아창원특수강",
    title: str = "원본제목",
    requirements: str = "원본요구사항",
    processing_content: Optional[str] = None,
    refined_title: Optional[str] = None,
    refined_overview: Optional[str] = None,
    refined_content: Optional[str] = None,
) -> ProcessedRecord:
    return ProcessedRecord(
        request_id=request_id,
        status=status,
        schedule=schedule,
        category=category,
        company=company,
        title=title,
        requirements=requirements,
        processing_content=processing_content,
        refined_title=refined_title,
        refined_overview=refined_overview,
        refined_content=refined_content,
    )


def run(coro):
    """비동기 포매터를 동기 테스트에서 실행하는 유틸."""
    return asyncio.get_event_loop().run_until_complete(coro)


def fmt(records: list[ProcessedRecord]) -> str:
    """편의 래퍼: 레코드 리스트 → 결과 텍스트."""
    formatter = WeeklyReportFormatter()
    output = run(formatter.format(WeeklyReportFormatterInput(records=records)))
    return output.result_text


# ====================
# TC-1: 데이터 없음
# ====================


def test_tc1_empty_records_returns_empty_string():
    result = fmt([])
    assert result == ""


# ====================
# TC-2: 창원만 있는 경우
# ====================


def test_tc2_only_changwon_no_besteel_section():
    records = [make_record(company="세아창원특수강")]
    result = fmt(records)

    assert "◈EPRO 운영" in result
    assert "[창원]" in result
    assert "[베스틸]" not in result


# ====================
# TC-3: 베스틸만 있는 경우
# ====================


def test_tc3_only_besteel_no_changwon_section():
    records = [make_record(company="세아베스틸")]
    result = fmt(records)

    assert "◈EPRO 운영" in result
    assert "[베스틸]" in result
    assert "[창원]" not in result


# ====================
# TC-4: 두 섹션 모두 있는 경우
# ====================


def test_tc4_both_sections_present_and_ordered():
    records = [
        make_record(company="세아창원특수강", request_id="CW-001"),
        make_record(company="세아베스틸", request_id="BS-001"),
    ]
    result = fmt(records)

    assert "◈EPRO 운영" in result
    assert "[창원]" in result
    assert "[베스틸]" in result
    # 창원이 베스틸보다 먼저 등장해야 한다
    assert result.index("[창원]") < result.index("[베스틸]")
    # 헤더는 맨 앞
    assert result.startswith("◈EPRO 운영")


# ====================
# TC-5: -. 내용 라인 생략 (processing_content 없음)
# ====================


def test_tc5_no_content_omits_content_line():
    records = [make_record(processing_content=None, refined_content=None)]
    result = fmt(records)

    assert "-. 내용 :" not in result
    assert "-. 개요 :" in result


# ====================
# TC-6: -. 내용 라인 포함 (processing_content 있음)
# ====================


def test_tc6_with_processing_content_includes_content_line():
    records = [make_record(processing_content="처리내용 원본")]
    result = fmt(records)

    assert "  -. 내용 : 처리내용 원본" in result


def test_tc6b_with_refined_content_uses_refined():
    records = [
        make_record(
            processing_content="원본내용",
            refined_content="Gemini 윤문 내용",
        )
    ]
    result = fmt(records)

    assert "  -. 내용 : Gemini 윤문 내용" in result
    assert "원본내용" not in result


# ====================
# TC-7: refined_* 필드 우선, 없으면 원본 fallback
# ====================


def test_tc7_refined_fields_take_priority():
    records = [
        make_record(
            title="원본제목",
            requirements="원본요구사항",
            processing_content="원본내용",
            refined_title="Gemini제목",
            refined_overview="Gemini개요",
            refined_content="Gemini내용",
        )
    ]
    result = fmt(records)

    assert "Gemini제목" in result
    assert "Gemini개요" in result
    assert "Gemini내용" in result
    assert "원본제목" not in result
    assert "원본요구사항" not in result
    assert "원본내용" not in result


def test_tc7b_fallback_to_original_when_refined_is_none():
    records = [
        make_record(
            title="원본제목",
            requirements="원본요구사항",
            processing_content="원본내용",
            refined_title=None,
            refined_overview=None,
            refined_content=None,
        )
    ]
    result = fmt(records)

    assert "원본제목" in result
    assert "원본요구사항" in result
    assert "원본내용" in result


# ====================
# TC-8: schedule=None → 일정 부분 생략
# ====================


def test_tc8_schedule_none_omits_schedule_part():
    records = [
        make_record(
            schedule=None,
            status="진행중",
            category="프로젝트/운영",
            request_id="REQ-000",
            title="제목없일정",
        )
    ]
    result = fmt(records)

    # 일정 없는 경우: (진행상태) 형태로 끝나야 함
    assert "(진행중)" in result
    # 쉼표(,)가 진행상태 앞에 없어야 함 (일정이 없으므로)
    assert ", 진행중" not in result


def test_tc8b_schedule_present_includes_schedule():
    records = [make_record(schedule="~03/07", status="완료")]
    result = fmt(records)

    assert "(~03/07, 완료)" in result


# ====================
# TC-9: 한 섹션에 여러 항목 → 항목 간 빈 줄
# ====================


def test_tc9_multiple_items_in_section_separated_by_blank_line():
    records = [
        make_record(company="세아창원특수강", request_id="CW-001", title="첫번째"),
        make_record(company="세아창원특수강", request_id="CW-002", title="두번째"),
        make_record(company="세아창원특수강", request_id="CW-003", title="세번째"),
    ]
    result = fmt(records)

    # 첫번째, 두번째 항목 사이에 빈 줄이 있어야 한다
    # ▣ 라인이 연속으로 붙어 있으면 안 됨 (사이에 \n\n 필요)
    lines = result.split("\n")
    item_line_indices = [i for i, line in enumerate(lines) if line.startswith("▣")]
    assert len(item_line_indices) == 3, f"항목이 3개 있어야 함, 실제: {len(item_line_indices)}"

    for idx in range(len(item_line_indices) - 1):
        cur = item_line_indices[idx]
        nxt = item_line_indices[idx + 1]
        # 두 ▣ 라인 사이에 빈 줄("") 이 1개 이상 있어야 함
        between_lines = lines[cur + 1 : nxt]
        assert "" in between_lines, (
            f"항목 {idx+1}과 {idx+2} 사이에 빈 줄이 없음: {between_lines}"
        )


# ====================
# TC-10: 복합 케이스 (창원·베스틸 혼재 + 내용 없는 항목 혼재)
# ====================


def test_tc10_mixed_complex_case():
    records = [
        # 창원 - 내용 있음
        make_record(
            company="세아창원특수강",
            request_id="CW-001",
            title="창원제목1",
            processing_content="창원처리내용1",
        ),
        # 창원 - 내용 없음
        make_record(
            company="세아창원특수강",
            request_id="CW-002",
            title="창원제목2",
            processing_content=None,
        ),
        # 베스틸 - 내용 있음 (refined)
        make_record(
            company="세아베스틸",
            request_id="BS-001",
            title="베스틸원본제목",
            refined_title="베스틸Gemini제목",
            processing_content="베스틸원본내용",
            refined_content="베스틸Gemini내용",
        ),
    ]
    result = fmt(records)

    # 전체 구조 확인
    assert result.startswith("◈EPRO 운영")
    assert "[창원]" in result
    assert "[베스틸]" in result

    # 창원 섹션: 내용 있는 항목만 -. 내용 포함
    assert "창원처리내용1" in result

    # 창원 CW-002는 내용 없으므로 해당 항목 뒤에 -. 내용 없음을 확인
    # CW-002 ▣ 라인과 다음 항목(BS-001 ▣ 라인 또는 섹션) 사이에서 내용 없음 검증
    cw002_idx = result.index("CW-002")
    # CW-002 이후 다음 ▣ 또는 [베스틸] 전까지 "-. 내용 :" 없어야 함
    rest_after_cw002 = result[cw002_idx:]
    next_section_or_item = min(
        rest_after_cw002.find("[베스틸]") if "[베스틸]" in rest_after_cw002 else len(rest_after_cw002),
        rest_after_cw002.find("\n▣") if "\n▣" in rest_after_cw002 else len(rest_after_cw002),
    )
    cw002_block = rest_after_cw002[:next_section_or_item]
    assert "-. 내용 :" not in cw002_block, f"CW-002 블록에 내용 라인이 있으면 안 됨:\n{cw002_block}"

    # 베스틸: refined 필드 사용
    assert "베스틸Gemini제목" in result
    assert "베스틸Gemini내용" in result
    assert "베스틸원본제목" not in result


# ====================
# TC-11: company 부분 문자열 분류
# ====================


def test_tc11_company_substring_classification():
    # '창원'이 포함된 다양한 company 값
    changwon_companies = ["세아창원특수강", "창원공장", "창원 법인"]
    for company in changwon_companies:
        records = [make_record(company=company)]
        result = fmt(records)
        assert "[창원]" in result, f"company='{company}' 는 [창원] 섹션이어야 함"
        assert "[베스틸]" not in result

    # '베스틸'이 포함된 다양한 company 값
    besteel_companies = ["세아베스틸", "베스틸 본사", "베스틸강판"]
    for company in besteel_companies:
        records = [make_record(company=company)]
        result = fmt(records)
        assert "[베스틸]" in result, f"company='{company}' 는 [베스틸] 섹션이어야 함"
        assert "[창원]" not in result


# ====================
# TC-12: ▣ 라인 포맷 정확도
# ====================


def test_tc12_item_line_exact_format_with_schedule():
    records = [
        make_record(
            category="개발/개선",
            request_id="REQ-999",
            title="테스트제목",
            schedule="~12/31",
            status="완료",
            requirements="개요텍스트",
            processing_content="내용텍스트",
        )
    ]
    result = fmt(records)

    expected_header = "▣ (개발/개선) (REQ-999) 테스트제목 (~12/31, 완료)"
    expected_overview = "  -. 개요 : 개요텍스트"
    expected_content = "  -. 내용 : 내용텍스트"

    assert expected_header in result
    assert expected_overview in result
    assert expected_content in result


def test_tc12b_item_line_exact_format_without_schedule():
    records = [
        make_record(
            category="프로젝트/운영",
            request_id="REQ-100",
            title="일정없는항목",
            schedule=None,
            status="대기",
            requirements="개요텍스트",
        )
    ]
    result = fmt(records)

    expected_header = "▣ (프로젝트/운영) (REQ-100) 일정없는항목 (대기)"
    assert expected_header in result


# ====================
# TC-13: 섹션 간 빈 줄 (두 섹션 모두 있을 때)
# ====================


def test_tc13_blank_line_between_sections():
    records = [
        make_record(company="세아창원특수강", request_id="CW-001"),
        make_record(company="세아베스틸", request_id="BS-001"),
    ]
    result = fmt(records)

    # [창원] 섹션 끝과 [베스틸] 섹션 사이에 빈 줄이 있어야 함
    # 즉 result 안에 "\n\n[베스틸]" 패턴이 있어야 함
    assert "\n\n[베스틸]" in result


# ====================
# TC-14: 두 섹션 모두 분류 불가한 레코드만 있는 경우
# ====================


def test_tc14_unknown_company_excluded_from_output():
    # '창원' 도 '베스틸' 도 포함하지 않는 company
    records = [make_record(company="삼성전자")]
    result = fmt(records)

    # 섹션이 비어 있으므로 빈 문자열 반환
    assert result == ""

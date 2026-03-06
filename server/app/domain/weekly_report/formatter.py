"""
WeeklyReportFormatter: 계산된 레코드 리스트를 최종 텍스트 포맷으로 변환

Task 2-1 구현 범위:
    - ◈EPRO 운영 헤더 + [창원] / [베스틸] 섹션 포맷 생성
    - refined_* 필드 우선, 없으면 원본 필드 fallback
    - 처리내용 없는 항목에서 -. 내용 라인 생략 (줄바꿈 포함 생략)
    - 해당 회사 건이 없으면 섹션 헤더 전체 생략
    - 레코드가 없으면 빈 문자열 반환
"""

from __future__ import annotations

from server.app.domain.weekly_report.calculator import ProcessedRecord
from server.app.shared.base.formatter import BaseFormatter
from server.app.shared.types import FormatterInput, FormatterOutput


# ====================
# Input / Output 모델
# ====================


class WeeklyReportFormatterInput(FormatterInput):
    """WeeklyReportFormatter 입력 모델."""

    records: list[ProcessedRecord]


class WeeklyReportFormatterOutput(FormatterOutput):
    """WeeklyReportFormatter 출력 모델."""

    result_text: str


# ====================
# Formatter 구현
# ====================


class WeeklyReportFormatter(
    BaseFormatter[WeeklyReportFormatterInput, WeeklyReportFormatterOutput]
):
    """
    ProcessedRecord 리스트 → 최종 텍스트 포맷 변환기 (Task 2-1)

    출력 포맷 예시:
        ◈EPRO 운영
        [창원]
        ▣ ({구분}) ({요청 ID}) {제목} (~{mm/dd}, {진행상태})
          -. 개요 : {개요}
          -. 내용 : {내용}

        [베스틸]
        ▣ ({구분}) ({요청 ID}) {제목} ({진행상태})
          -. 개요 : {개요}

    분류 기준:
        - '창원' in company → [창원] 섹션
        - '베스틸' in company → [베스틸] 섹션

    조건부 처리:
        - refined_content 또는 processing_content 중 하나라도 있으면 -. 내용 라인 포함
        - 해당 회사 건이 없으면 섹션 헤더 전체 생략
        - schedule 없으면 ▣ 라인에서 일정 부분 생략
    """

    async def format(
        self, input_data: WeeklyReportFormatterInput
    ) -> WeeklyReportFormatterOutput:
        result_text = self._format_records(input_data.records)
        return WeeklyReportFormatterOutput(result_text=result_text)

    # --------------------------------------------------
    # Private helpers
    # --------------------------------------------------

    def _format_records(self, records: list[ProcessedRecord]) -> str:
        """레코드 리스트 전체를 최종 텍스트로 변환한다."""
        if not records:
            return ""

        changwon_records = [r for r in records if "창원" in r.company]
        besteel_records = [r for r in records if "베스틸" in r.company]

        sections: list[str] = []

        if changwon_records:
            changwon_items = "\n\n".join(
                self._format_item(r) for r in changwon_records
            )
            sections.append(f"[창원]\n{changwon_items}")

        if besteel_records:
            besteel_items = "\n\n".join(
                self._format_item(r) for r in besteel_records
            )
            sections.append(f"[베스틸]\n{besteel_items}")

        if not sections:
            return ""

        body = "\n\n".join(sections)
        return f"◈EPRO 운영\n{body}"

    def _format_item(self, record: ProcessedRecord) -> str:
        """단일 ProcessedRecord 를 ▣ 블록 문자열로 변환한다."""
        title = record.refined_title or record.title
        overview = record.refined_overview or record.requirements
        content = record.refined_content or record.processing_content

        # ▣ 헤더 라인: schedule 없으면 일정 부분 생략
        if record.schedule:
            header = (
                f"▣ ({record.category}) ({record.request_id}) {title}"
                f" ({record.schedule}, {record.status})"
            )
        else:
            header = (
                f"▣ ({record.category}) ({record.request_id}) {title}"
                f" ({record.status})"
            )

        lines = [header]
        lines.append(f"  -. 개요 : {overview}")

        # -. 내용 라인: content 없으면 줄바꿈 없이 생략
        if content:
            lines.append(f"  -. 내용 : {content}")

        return "\n".join(lines)

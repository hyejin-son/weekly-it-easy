"""
WeeklyReport API 통합 테스트 (Task 2-2)

테스트 범위:
    POST /api/v1/weekly-report/generate

    - 확장자 오류 파일 → 400 응답
    - 컬럼 부족 파일  → 400 응답
    - 정상 파일 + mock → 200 응답 + result_text 반환
    - 파일 누락       → 422 응답 (FastAPI 자동 검증)
"""

from __future__ import annotations

import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from server.app.domain.weekly_report.calculator import MIN_REQUIRED_COLS


# ====================
# 공통 헬퍼
# ====================


def make_excel_bytes(n_cols: int = MIN_REQUIRED_COLS, n_data_rows: int = 1) -> bytes:
    """
    pd.read_excel(header=2) 호환 Excel bytes를 생성한다.
    row 0, 1: 더미(건너뜀), row 2: 컬럼명(header), row 3~: 데이터
    """
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active

    ws.append(["dummy"] * n_cols)
    ws.append(["dummy"] * n_cols)
    ws.append([f"col_{i}" for i in range(n_cols)])
    for _ in range(n_data_rows):
        ws.append(["value"] * n_cols)

    wb.save(buf)
    buf.seek(0)
    return buf.read()


def build_multipart_files(
    ab1_name: str = "ab1.xlsx",
    ab1_bytes: bytes | None = None,
    ab2_name: str = "ab2.xlsx",
    ab2_bytes: bytes | None = None,
    cd1_name: str = "cd1.xlsx",
    cd1_bytes: bytes | None = None,
    cd2_name: str = "cd2.xlsx",
    cd2_bytes: bytes | None = None,
    n_cols: int = MIN_REQUIRED_COLS,
) -> dict:
    """TestClient에 전달할 multipart files 딕셔너리를 구성한다."""
    default_bytes = make_excel_bytes(n_cols)
    return {
        "file_ab_1": (ab1_name, io.BytesIO(ab1_bytes if ab1_bytes is not None else default_bytes), "application/octet-stream"),
        "file_ab_2": (ab2_name, io.BytesIO(ab2_bytes if ab2_bytes is not None else default_bytes), "application/octet-stream"),
        "file_cd_1": (cd1_name, io.BytesIO(cd1_bytes if cd1_bytes is not None else default_bytes), "application/octet-stream"),
        "file_cd_2": (cd2_name, io.BytesIO(cd2_bytes if cd2_bytes is not None else default_bytes), "application/octet-stream"),
    }


# ====================
# 테스트 클래스
# ====================


class TestGenerateWeeklyReport:
    """POST /api/v1/weekly-report/generate 엔드포인트 통합 테스트."""

    ENDPOINT = "/api/v1/weekly-report/generate"

    # --------------------------------------------------
    # 422: 필수 파라미터 누락
    # --------------------------------------------------

    def test_missing_all_params_returns_422(self, client: TestClient) -> None:
        """파라미터가 전혀 없으면 FastAPI 자동 검증 오류(422)를 반환해야 한다."""
        resp = client.post(self.ENDPOINT)
        assert resp.status_code == 422

    def test_missing_files_returns_422(self, client: TestClient) -> None:
        """report_date만 전달하고 파일 없으면 422를 반환해야 한다."""
        resp = client.post(self.ENDPOINT, data={"report_date": "2024-12-13"})
        assert resp.status_code == 422

    # --------------------------------------------------
    # 400: 확장자 오류
    # --------------------------------------------------

    def test_invalid_extension_returns_400(self, client: TestClient) -> None:
        """.txt 확장자 파일을 전달하면 400을 반환해야 한다."""
        files = build_multipart_files(ab1_name="report.txt")
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body

    def test_csv_extension_returns_400(self, client: TestClient) -> None:
        """.csv 확장자 파일을 전달하면 400을 반환해야 한다."""
        files = build_multipart_files(
            cd2_name="data.csv",
            cd2_bytes=b"col1,col2\nval1,val2",
        )
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )
        assert resp.status_code == 400

    # --------------------------------------------------
    # 400: 컬럼 부족
    # --------------------------------------------------

    def test_insufficient_columns_returns_400(self, client: TestClient) -> None:
        """컬럼 수가 MIN_REQUIRED_COLS 미만이면 400을 반환해야 한다."""
        files = build_multipart_files(n_cols=5)
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body

    # --------------------------------------------------
    # 200: 정상 흐름 (Calculator / Formatter mock)
    # --------------------------------------------------

    def test_success_returns_200_with_result_text(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        정상 파일 + mock Calculator + mock Formatter → 200 + result_text 반환.
        """
        from server.app.domain.weekly_report.calculator import (
            WeeklyReportCalculatorOutput,
        )
        from server.app.domain.weekly_report.formatter import (
            WeeklyReportFormatterOutput,
        )
        from server.app.domain.weekly_report import calculator as calc_mod
        from server.app.domain.weekly_report import formatter as fmt_mod

        async def mock_calculate(self_inner, input_data):
            return WeeklyReportCalculatorOutput(records=[])

        async def mock_format(self_inner, input_data):
            return WeeklyReportFormatterOutput(result_text="◈EPRO 운영\n[창원]\n▣ 테스트 항목")

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "calculate", mock_calculate)
        monkeypatch.setattr(fmt_mod.WeeklyReportFormatter, "format", mock_format)

        files = build_multipart_files()
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "result_text" in body
        assert "◈EPRO 운영" in body["result_text"]

    def test_success_response_schema(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """응답 JSON이 WeeklyReportResponse 스키마 형태를 따라야 한다."""
        from server.app.domain.weekly_report.calculator import (
            WeeklyReportCalculatorOutput,
        )
        from server.app.domain.weekly_report.formatter import (
            WeeklyReportFormatterOutput,
        )
        from server.app.domain.weekly_report import calculator as calc_mod
        from server.app.domain.weekly_report import formatter as fmt_mod

        async def mock_calculate(self_inner, input_data):
            return WeeklyReportCalculatorOutput(records=[])

        async def mock_format(self_inner, input_data):
            return WeeklyReportFormatterOutput(result_text="결과 텍스트")

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "calculate", mock_calculate)
        monkeypatch.setattr(fmt_mod.WeeklyReportFormatter, "format", mock_format)

        files = build_multipart_files()
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )

        assert resp.status_code == 200
        body = resp.json()
        # WeeklyReportResponse 스키마: result_text 키 하나만 있어야 함
        assert set(body.keys()) == {"result_text"}
        assert isinstance(body["result_text"], str)

    def test_empty_result_text_is_valid(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """records가 없으면 result_text=""를 반환해야 한다 (Formatter 스펙)."""
        from server.app.domain.weekly_report.calculator import (
            WeeklyReportCalculatorOutput,
        )
        from server.app.domain.weekly_report.formatter import (
            WeeklyReportFormatterOutput,
        )
        from server.app.domain.weekly_report import calculator as calc_mod
        from server.app.domain.weekly_report import formatter as fmt_mod

        async def mock_calculate(self_inner, input_data):
            return WeeklyReportCalculatorOutput(records=[])

        async def mock_format(self_inner, input_data):
            return WeeklyReportFormatterOutput(result_text="")

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "calculate", mock_calculate)
        monkeypatch.setattr(fmt_mod.WeeklyReportFormatter, "format", mock_format)

        files = build_multipart_files()
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )

        assert resp.status_code == 200
        assert resp.json()["result_text"] == ""

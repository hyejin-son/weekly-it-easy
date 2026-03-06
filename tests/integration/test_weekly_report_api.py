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


# ====================
# Task 4-1: POST /extract 통합 테스트
# ====================


class TestExtractWeeklyReport:
    """POST /api/v1/weekly-report/extract 엔드포인트 통합 테스트 (Task 4-1)."""

    ENDPOINT = "/api/v1/weekly-report/extract"

    # --------------------------------------------------
    # 422: 필수 파라미터 누락
    # --------------------------------------------------

    def test_missing_all_params_returns_422(self, client: TestClient) -> None:
        """파라미터가 전혀 없으면 422를 반환해야 한다."""
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
        assert "detail" in resp.json()

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
        assert "detail" in resp.json()

    # --------------------------------------------------
    # 200: 정상 흐름 (extract mock)
    # --------------------------------------------------

    def test_success_returns_200_with_records_list(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """정상 파일 + mock extract → 200 + records 배열 반환."""
        from server.app.domain.weekly_report import calculator as calc_mod
        from server.app.domain.weekly_report.schemas import WeeklyReportRecord

        sample_record = WeeklyReportRecord(
            request_id="REQ-001",
            company="세아창원특수강",
            biz_system="세아창원특수강>기타>e-Procurement",
            biz_system2="",
            category="개발/개선",
            status="완료",
            schedule="~12/13",
            title_raw="테스트 제목",
            summary_raw="테스트 요구사항",
            content_raw="테스트 처리내용",
        )

        async def mock_extract(self_inner, input_data):
            return [sample_record]

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "extract", mock_extract)

        files = build_multipart_files()
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "records" in body
        assert isinstance(body["records"], list)
        assert len(body["records"]) == 1

    def test_success_response_schema(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """응답 JSON이 ExtractResponse 스키마를 따라야 한다 (records 키 + 10개 필드)."""
        from server.app.domain.weekly_report import calculator as calc_mod
        from server.app.domain.weekly_report.schemas import WeeklyReportRecord

        sample_record = WeeklyReportRecord(
            request_id="REQ-002",
            company="세아베스틸",
            biz_system="세아베스틸>기타>e-Procurement",
            biz_system2="세아베스틸>기타>e-Procurement",
            category="프로젝트/운영",
            status="진행중",
            schedule="",
            title_raw="스키마 검증 제목",
            summary_raw="스키마 검증 요구사항",
            content_raw=None,
        )

        async def mock_extract(self_inner, input_data):
            return [sample_record]

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "extract", mock_extract)

        files = build_multipart_files()
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"records"}
        assert isinstance(body["records"], list)

        record = body["records"][0]
        expected_fields = {
            "request_id", "company", "biz_system", "biz_system2",
            "category", "status", "schedule", "title_raw", "summary_raw", "content_raw",
        }
        assert set(record.keys()) == expected_fields
        assert record["content_raw"] is None

    def test_empty_records_is_valid(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """필터 조건에 맞는 레코드가 없으면 records=[] 을 반환해야 한다."""
        from server.app.domain.weekly_report import calculator as calc_mod

        async def mock_extract(self_inner, input_data):
            return []

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "extract", mock_extract)

        files = build_multipart_files()
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body == {"records": []}

    def test_no_gemini_call_fast_response(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        extract는 Gemini를 호출하지 않으므로 2초 이내에 응답해야 한다.
        _refine_records_batch가 호출되면 즉시 AssertionError를 발생시켜 검출한다.
        """
        import time
        from server.app.domain.weekly_report import calculator as calc_mod

        async def mock_extract(self_inner, input_data):
            return []

        async def must_not_be_called(*args, **kwargs):
            raise AssertionError("extract() 내에서 Gemini(_refine_records_batch)가 호출되었습니다!")

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "extract", mock_extract)
        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "_refine_records_batch", must_not_be_called)

        files = build_multipart_files()
        start = time.monotonic()
        resp = client.post(
            self.ENDPOINT,
            data={"report_date": "2024-12-13"},
            files=files,
        )
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 2.0, f"extract API가 {elapsed:.2f}초로 2초를 초과했습니다."

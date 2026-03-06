"""
WeeklyReportService 단위 테스트 (Task 2-2)

테스트 범위:
    - 확장자 검증: .xlsx/.xls 이외 → HTTPException(400)
    - 컬럼 수 검증: MIN_REQUIRED_COLS 미만 → HTTPException(400)
    - 정상 검증 통과: 올바른 파일 → 에러 없음
    - execute() 정상 흐름: Calculator/Formatter mock → ServiceResult.ok
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from fastapi import HTTPException

from server.app.domain.weekly_report.calculator import MIN_REQUIRED_COLS
from server.app.domain.weekly_report.service import (
    VALID_EXTENSIONS,
    WeeklyReportService,
    WeeklyReportServiceInput,
)


# ====================
# 헬퍼 함수
# ====================


def make_excel_bytes(n_cols: int = MIN_REQUIRED_COLS, n_data_rows: int = 1) -> bytes:
    """
    pd.read_excel(header=2)에서 n_cols 개의 컬럼을 갖는 Excel bytes를 생성한다.

    header=2 이므로 row 0, 1은 더미(건너뜀), row 2가 헤더 행이 된다.
    실제 구조: 3개 헤더 행 + n_data_rows 데이터 행
    """
    buf = io.BytesIO()
    # 헤더 행 2개(더미) + 실제 컬럼명 1개 = 총 3행을 header로 처리
    # openpyxl을 통해 직접 시트를 구성한다
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active

    # row 1, 2: 더미 행
    ws.append(["dummy"] * n_cols)
    ws.append(["dummy"] * n_cols)
    # row 3: 실제 컬럼명 (header=2 이므로 이 행이 헤더로 읽힘)
    ws.append([f"col_{i}" for i in range(n_cols)])
    # 데이터 행
    for _ in range(n_data_rows):
        ws.append(["value"] * n_cols)

    wb.save(buf)
    buf.seek(0)
    return buf.read()


def make_service_input(
    ab1_name: str = "ab1.xlsx",
    ab2_name: str = "ab2.xlsx",
    cd1_name: str = "cd1.xlsx",
    cd2_name: str = "cd2.xlsx",
    n_cols: int = MIN_REQUIRED_COLS,
) -> WeeklyReportServiceInput:
    """정상 또는 커스텀 WeeklyReportServiceInput을 만든다."""
    file_bytes = make_excel_bytes(n_cols)
    return WeeklyReportServiceInput(
        report_date="2024-12-13",
        file_ab_1_name=ab1_name,
        file_ab_1_bytes=file_bytes,
        file_ab_2_name=ab2_name,
        file_ab_2_bytes=file_bytes,
        file_cd_1_name=cd1_name,
        file_cd_1_bytes=file_bytes,
        file_cd_2_name=cd2_name,
        file_cd_2_bytes=file_bytes,
    )


# ====================
# 확장자 검증 테스트
# ====================


class TestValidateExtensions:
    """_validate_extensions() 동작 검증."""

    def _svc(self) -> WeeklyReportService:
        return WeeklyReportService()

    @pytest.mark.parametrize("ext", [".xlsx", ".xls"])
    def test_valid_extension_passes(self, ext: str) -> None:
        """허용 확장자(.xlsx, .xls)는 에러 없이 통과해야 한다."""
        svc = self._svc()
        request = make_service_input(
            ab1_name=f"file{ext}",
            ab2_name=f"file{ext}",
            cd1_name=f"file{ext}",
            cd2_name=f"file{ext}",
        )
        # 에러 없이 반환되면 통과
        svc._validate_extensions(request)

    @pytest.mark.parametrize("bad_name", [
        "report.txt",
        "data.csv",
        "document.pdf",
        "image.png",
        "noextension",
    ])
    def test_invalid_extension_raises_400(self, bad_name: str) -> None:
        """비허용 확장자 파일이 1개라도 있으면 HTTPException(400)이 발생해야 한다."""
        svc = self._svc()
        request = make_service_input(ab1_name=bad_name)
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_extensions(request)
        assert exc_info.value.status_code == 400

    def test_mixed_valid_invalid_raises_400(self) -> None:
        """4개 중 1개가 잘못된 확장자면 400이 발생해야 한다."""
        svc = self._svc()
        request = make_service_input(
            ab1_name="ok.xlsx",
            ab2_name="ok.xlsx",
            cd1_name="ok.xlsx",
            cd2_name="bad.csv",  # 마지막 파일만 잘못됨
        )
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_extensions(request)
        assert exc_info.value.status_code == 400

    def test_uppercase_extension_is_accepted(self) -> None:
        """대문자 확장자(.XLSX)도 허용되어야 한다 (대소문자 무시)."""
        svc = self._svc()
        request = make_service_input(
            ab1_name="FILE.XLSX",
            ab2_name="FILE.XLS",
            cd1_name="FILE.xlsx",
            cd2_name="FILE.xls",
        )
        # 에러 없이 통과
        svc._validate_extensions(request)


# ====================
# 컬럼 수 검증 테스트
# ====================


class TestValidateColumns:
    """_validate_columns() 동작 검증."""

    def _svc(self) -> WeeklyReportService:
        return WeeklyReportService()

    def test_sufficient_columns_pass(self) -> None:
        """MIN_REQUIRED_COLS 이상이면 에러 없이 통과해야 한다."""
        svc = self._svc()
        request = make_service_input(n_cols=MIN_REQUIRED_COLS)
        svc._validate_columns(request)

    def test_extra_columns_pass(self) -> None:
        """컬럼이 더 많은 경우(30개)도 통과해야 한다."""
        svc = self._svc()
        request = make_service_input(n_cols=30)
        svc._validate_columns(request)

    def test_insufficient_columns_raises_400(self) -> None:
        """컬럼 수가 MIN_REQUIRED_COLS 미만이면 HTTPException(400)이 발생해야 한다."""
        svc = self._svc()
        request = make_service_input(n_cols=MIN_REQUIRED_COLS - 1)
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_columns(request)
        assert exc_info.value.status_code == 400

    def test_empty_bytes_raises_400(self) -> None:
        """빈 bytes는 읽기 불가 → HTTPException(400)이 발생해야 한다."""
        svc = self._svc()
        request = make_service_input()
        request.file_ab_1_bytes = b""
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_columns(request)
        assert exc_info.value.status_code == 400

    def test_non_excel_bytes_raises_400(self) -> None:
        """Excel이 아닌 바이너리 데이터는 읽기 실패 → HTTPException(400)이 발생해야 한다."""
        svc = self._svc()
        request = make_service_input()
        request.file_ab_2_bytes = b"NOT AN EXCEL FILE - RANDOM BYTES \x00\x01\x02"
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_columns(request)
        assert exc_info.value.status_code == 400


# ====================
# execute() 흐름 테스트 (mock)
# ====================


class TestExecute:
    """execute() 전체 흐름 검증 (Calculator/Formatter mock)."""

    @pytest.mark.asyncio
    async def test_execute_invalid_extension_raises_http_exception(self) -> None:
        """
        확장자 오류 시 execute()가 HTTPException을 전파해야 한다.
        (ServiceResult.fail이 아니라 HTTPException raise)
        """
        svc = WeeklyReportService()
        request = make_service_input(ab1_name="bad.csv")
        with pytest.raises(HTTPException) as exc_info:
            await svc.execute(request)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_insufficient_columns_raises_http_exception(self) -> None:
        """컬럼 부족 시 execute()가 HTTPException을 전파해야 한다."""
        svc = WeeklyReportService()
        request = make_service_input(n_cols=5)
        with pytest.raises(HTTPException) as exc_info:
            await svc.execute(request)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_success_with_mocked_calculator_and_formatter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        검증 통과 후 Calculator → Formatter 파이프라인이 정상 동작하면
        ServiceResult.ok(WeeklyReportResponse)를 반환해야 한다.
        """
        from server.app.domain.weekly_report.calculator import (
            WeeklyReportCalculatorOutput,
        )
        from server.app.domain.weekly_report.formatter import (
            WeeklyReportFormatterOutput,
        )

        # Calculator mock: records=[] 반환
        async def mock_calculate(self_inner, input_data):
            return WeeklyReportCalculatorOutput(records=[])

        # Formatter mock: 빈 result_text 반환
        async def mock_format(self_inner, input_data):
            return WeeklyReportFormatterOutput(result_text="◈EPRO 운영\n[창원]\n테스트 항목")

        from server.app.domain.weekly_report import calculator as calc_mod
        from server.app.domain.weekly_report import formatter as fmt_mod

        monkeypatch.setattr(calc_mod.WeeklyReportCalculator, "calculate", mock_calculate)
        monkeypatch.setattr(fmt_mod.WeeklyReportFormatter, "format", mock_format)

        svc = WeeklyReportService()
        request = make_service_input()

        result = await svc.execute(request)

        assert result.success is True
        assert result.data is not None
        assert "◈EPRO 운영" in result.data.result_text

    @pytest.mark.asyncio
    async def test_execute_returns_fail_on_unexpected_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Calculator에서 예기치 않은 예외 발생 시
        ServiceResult.fail(error)를 반환해야 한다.
        """
        async def mock_calculate_error(self_inner, input_data):
            raise RuntimeError("Gemini API timeout")

        from server.app.domain.weekly_report import calculator as calc_mod
        monkeypatch.setattr(
            calc_mod.WeeklyReportCalculator, "calculate", mock_calculate_error
        )

        svc = WeeklyReportService()
        request = make_service_input()

        result = await svc.execute(request)

        assert result.success is False
        assert result.error is not None
        assert "Gemini API timeout" in result.error

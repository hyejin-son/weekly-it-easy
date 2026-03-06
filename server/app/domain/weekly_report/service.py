"""
WeeklyReportService: Calculator + Formatter 워크플로우 조율

Task 2-2 구현 범위:
    - 파일 확장자 검증 (.xlsx / .xls)
    - 컬럼 수 검증 (pd.read_excel header=2, MIN_REQUIRED_COLS 이상)
    - WeeklyReportCalculator → WeeklyReportFormatter 순서로 실행
    - 검증 실패 시 HTTPException(status_code=400) raise
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import HTTPException

from server.app.shared.base.service import BaseService
from server.app.shared.types import ServiceResult
from server.app.domain.weekly_report.calculator import (
    MIN_REQUIRED_COLS,
    WeeklyReportCalculator,
    WeeklyReportCalculatorInput,
)
from server.app.domain.weekly_report.formatter import (
    WeeklyReportFormatter,
    WeeklyReportFormatterInput,
)
from server.app.domain.weekly_report.schemas import ExtractResponse, WeeklyReportResponse

logger = logging.getLogger(__name__)

VALID_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".xls"})


# ====================
# Service Input 모델
# ====================


@dataclass
class WeeklyReportServiceInput:
    """
    WeeklyReportService.execute() 입력 모델.

    Router에서 UploadFile.read()로 읽은 bytes와
    원본 파일명을 함께 전달한다.
    """

    report_date: str
    file_ab_1_name: str
    file_ab_1_bytes: bytes
    file_ab_2_name: str
    file_ab_2_bytes: bytes
    file_cd_1_name: str
    file_cd_1_bytes: bytes
    file_cd_2_name: str
    file_cd_2_bytes: bytes


# ====================
# Service 구현
# ====================


class WeeklyReportService(BaseService[WeeklyReportServiceInput, WeeklyReportResponse]):
    """
    주간보고 생성 서비스 (Task 2-2)

    흐름:
        1. 확장자 검증   → 실패 시 HTTPException(400)
        2. 컬럼 수 검증  → 실패 시 HTTPException(400)
        3. Calculator 실행 (Excel 파싱 + Gemini 윤문)
        4. Formatter 실행 (텍스트 포맷팅)
        5. ServiceResult.ok(WeeklyReportResponse) 반환
    """

    def __init__(self, db: Optional[Any] = None) -> None:
        super().__init__(db)  # type: ignore[arg-type]
        self.calculator = WeeklyReportCalculator()
        self.formatter = WeeklyReportFormatter()

    async def execute(
        self,
        request: WeeklyReportServiceInput,
        **kwargs: Any,
    ) -> ServiceResult[WeeklyReportResponse]:
        try:
            # 1. 사전 검증
            self._validate_extensions(request)
            self._validate_columns(request)

            # 2. Calculator: Excel bytes → ProcessedRecord 리스트
            calc_output = await self.calculator.calculate(
                WeeklyReportCalculatorInput(
                    report_date=request.report_date,
                    file_ab_1=request.file_ab_1_bytes,
                    file_ab_2=request.file_ab_2_bytes,
                    file_cd_1=request.file_cd_1_bytes,
                    file_cd_2=request.file_cd_2_bytes,
                )
            )

            # 3. Formatter: ProcessedRecord 리스트 → 최종 텍스트
            fmt_output = await self.formatter.format(
                WeeklyReportFormatterInput(records=calc_output.records)
            )

            return ServiceResult.ok(
                WeeklyReportResponse(result_text=fmt_output.result_text)
            )

        except HTTPException:
            # 검증 에러는 그대로 전파 (FastAPI가 400 응답으로 처리)
            raise
        except Exception as exc:
            logger.exception("WeeklyReportService.execute 실패")
            return ServiceResult.fail(str(exc))

    async def extract_records(
        self,
        request: WeeklyReportServiceInput,
        **kwargs: Any,
    ) -> ServiceResult[ExtractResponse]:
        """
        Excel 파싱·필터링만 수행하고 WeeklyReportRecord 목록을 반환한다 (Task 4-1).

        Gemini 윤문을 수행하지 않으므로 즉시 응답이 가능하다.

        흐름:
            1. 확장자 검증   → 실패 시 HTTPException(400)
            2. 컬럼 수 검증  → 실패 시 HTTPException(400)
            3. Calculator.extract() 실행 (Excel 파싱만, Gemini 없음)
            4. ServiceResult.ok(ExtractResponse) 반환
        """
        try:
            self._validate_extensions(request)
            self._validate_columns(request)

            records = await self.calculator.extract(
                WeeklyReportCalculatorInput(
                    report_date=request.report_date,
                    file_ab_1=request.file_ab_1_bytes,
                    file_ab_2=request.file_ab_2_bytes,
                    file_cd_1=request.file_cd_1_bytes,
                    file_cd_2=request.file_cd_2_bytes,
                )
            )

            return ServiceResult.ok(ExtractResponse(records=records))

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("WeeklyReportService.extract_records 실패")
            return ServiceResult.fail(str(exc))

    # --------------------------------------------------
    # Private: 검증 메서드
    # --------------------------------------------------

    def _validate_extensions(self, request: WeeklyReportServiceInput) -> None:
        """4개 파일 모두 .xlsx 또는 .xls 확장자인지 확인한다."""
        file_names = [
            request.file_ab_1_name,
            request.file_ab_2_name,
            request.file_cd_1_name,
            request.file_cd_2_name,
        ]
        for name in file_names:
            ext = Path(name).suffix.lower()
            if ext not in VALID_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"지원하지 않는 파일 형식입니다: '{name}'. "
                        ".xlsx 또는 .xls 파일만 허용됩니다."
                    ),
                )

    def _validate_columns(self, request: WeeklyReportServiceInput) -> None:
        """
        각 파일을 pd.read_excel(header=2, nrows=0)로 읽어
        필수 컬럼 수(MIN_REQUIRED_COLS) 이상인지 확인한다.

        nrows=0: 헤더 행만 읽어 성능 최소화
        """
        files = [
            (request.file_ab_1_name, request.file_ab_1_bytes),
            (request.file_ab_2_name, request.file_ab_2_bytes),
            (request.file_cd_1_name, request.file_cd_1_bytes),
            (request.file_cd_2_name, request.file_cd_2_bytes),
        ]
        for name, file_bytes in files:
            try:
                df = pd.read_excel(
                    io.BytesIO(file_bytes),
                    header=2,
                    nrows=0,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"파일을 읽을 수 없습니다: '{name}'. ({exc})",
                ) from exc

            if len(df.columns) < MIN_REQUIRED_COLS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"파일 '{name}'의 컬럼 수({len(df.columns)})가 "
                        f"최소 요구 컬럼 수({MIN_REQUIRED_COLS})보다 적습니다. "
                        "지정된 양식의 엑셀 파일을 사용해 주세요."
                    ),
                )

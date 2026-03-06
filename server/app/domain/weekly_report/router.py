"""
WeeklyReport 라우터

Task 2-2 구현 범위:
    POST /api/v1/weekly-report/generate (Task 4-2에서 JSON body로 교체됨)

Task 4-1 구현 범위:
    POST /api/v1/weekly-report/extract
        - multipart/form-data 로 report_date + 4개 Excel 파일을 수신
        - Gemini 없이 파싱·필터링된 레코드 목록을 반환

Task 4-2 구현 범위:
    POST /api/v1/weekly-report/generate
        - application/json 으로 GenerateRequest(report_date, records)를 수신
        - WeeklyReportService.generate_report() 호출 (Gemini 윤문 + 포맷팅)
        - 성공 시 WeeklyReportResponse(result_text) 반환
"""

from __future__ import annotations

import io

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from server.app.domain.weekly_report.schemas import ExtractResponse, GenerateRequest, WeeklyReportResponse
from server.app.domain.weekly_report.service import (
    WeeklyReportService,
    WeeklyReportServiceInput,
)

router = APIRouter(
    prefix="/weekly-report",
    tags=["weekly-report"],
)


@router.post(
    "/generate",
    response_model=WeeklyReportResponse,
    status_code=200,
    summary="주간보고 생성 (Task 4-2)",
    description=(
        "/extract 단계에서 얻은 레코드 목록(GenerateRequest)을 JSON body로 전달하면 "
        "Gemini 윤문 + 포맷팅을 수행한 주간보고 텍스트를 반환합니다."
    ),
)
async def generate_weekly_report(
    request: GenerateRequest,
) -> WeeklyReportResponse:
    """
    추출된 레코드 JSON을 받아 Gemini 윤문 + 포맷팅된 주간보고 텍스트를 생성합니다.

    - 내부 처리 중 예기치 않은 오류 발생 시 **500** 응답
    """
    service = WeeklyReportService()
    result = await service.generate_report(request)

    if result.success:
        return result.data  # type: ignore[return-value]

    raise HTTPException(
        status_code=500,
        detail=f"주간보고 생성 중 오류가 발생했습니다: {result.error}",
    )


@router.post(
    "/extract",
    response_model=ExtractResponse,
    status_code=200,
    summary="주간보고 데이터 추출 (AI 없음)",
    description=(
        "4개의 Excel 파일(AB팀 2개, CD팀 2개)과 보고 날짜를 업로드하면 "
        "Gemini 윤문 없이 즉시 파싱·필터링된 레코드 목록을 반환합니다."
    ),
)
async def extract_weekly_report(
    report_date: str = Form(
        ...,
        description="보고 기준 날짜 (ISO 형식: YYYY-MM-DD)",
        example="2024-12-13",
    ),
    file_ab_1: UploadFile = File(..., description="AB팀 첫 번째 Excel 파일 (.xlsx/.xls)"),
    file_ab_2: UploadFile = File(..., description="AB팀 두 번째 Excel 파일 (.xlsx/.xls)"),
    file_cd_1: UploadFile = File(..., description="CD팀 첫 번째 Excel 파일 (.xlsx/.xls)"),
    file_cd_2: UploadFile = File(..., description="CD팀 두 번째 Excel 파일 (.xlsx/.xls)"),
) -> ExtractResponse:
    """
    Excel 파일을 파싱·필터링하여 구조화된 레코드 목록을 반환합니다 (Gemini 없음).

    - 파일 확장자가 .xlsx/.xls 가 아니거나 필수 컬럼이 부족하면 **400** 응답
    - 내부 처리 중 예기치 않은 오류 발생 시 **500** 응답
    """
    # 1. UploadFile → bytes
    ab_1_bytes = await file_ab_1.read()
    ab_2_bytes = await file_ab_2.read()
    cd_1_bytes = await file_cd_1.read()
    cd_2_bytes = await file_cd_2.read()

    # 2. Service 입력 모델 구성
    service_input = WeeklyReportServiceInput(
        report_date=report_date,
        file_ab_1_name=file_ab_1.filename or "file_ab_1",
        file_ab_1_bytes=ab_1_bytes,
        file_ab_2_name=file_ab_2.filename or "file_ab_2",
        file_ab_2_bytes=ab_2_bytes,
        file_cd_1_name=file_cd_1.filename or "file_cd_1",
        file_cd_1_bytes=cd_1_bytes,
        file_cd_2_name=file_cd_2.filename or "file_cd_2",
        file_cd_2_bytes=cd_2_bytes,
    )

    # 3. Service 실행 (Gemini 없이 즉시 반환)
    service = WeeklyReportService()
    result = await service.extract_records(service_input)

    if result.success:
        return result.data  # type: ignore[return-value]

    raise HTTPException(
        status_code=500,
        detail=f"데이터 추출 중 오류가 발생했습니다: {result.error}",
    )

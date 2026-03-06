"""
WeeklyReport 라우터

Task 2-2 구현 범위:
    POST /api/v1/weekly-report/generate
        - multipart/form-data 로 report_date + 4개 Excel 파일을 수신
        - await file.read() → bytes 변환 후 WeeklyReportService 호출
        - 성공 시 WeeklyReportResponse(result_text) 반환
"""

from __future__ import annotations

import io

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from server.app.domain.weekly_report.schemas import WeeklyReportResponse
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
    summary="주간보고 생성",
    description=(
        "4개의 Excel 파일(AB팀 2개, CD팀 2개)과 보고 날짜를 업로드하면 "
        "포맷팅된 주간보고 텍스트를 반환합니다."
    ),
)
async def generate_weekly_report(
    report_date: str = Form(
        ...,
        description="보고 기준 날짜 (ISO 형식: YYYY-MM-DD)",
        example="2024-12-13",
    ),
    file_ab_1: UploadFile = File(..., description="AB팀 첫 번째 Excel 파일 (.xlsx/.xls)"),
    file_ab_2: UploadFile = File(..., description="AB팀 두 번째 Excel 파일 (.xlsx/.xls)"),
    file_cd_1: UploadFile = File(..., description="CD팀 첫 번째 Excel 파일 (.xlsx/.xls)"),
    file_cd_2: UploadFile = File(..., description="CD팀 두 번째 Excel 파일 (.xlsx/.xls)"),
) -> WeeklyReportResponse:
    """
    주간보고 텍스트를 생성합니다.

    - 파일 확장자가 .xlsx/.xls 가 아니거나 필수 컬럼이 부족하면 **400** 응답
    - 내부 처리 중 예기치 않은 오류 발생 시 **500** 응답
    """
    # 1. UploadFile → bytes (await 비동기 읽기)
    ab_1_bytes = await file_ab_1.read()
    ab_2_bytes = await file_ab_2.read()
    cd_1_bytes = await file_cd_1.read()
    cd_2_bytes = await file_cd_2.read()

    # 2. Service 입력 모델 구성 (bytes + 원본 파일명 전달)
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

    # 3. Service 실행
    #    - HTTPException(400): service._validate_* 에서 직접 raise → FastAPI 자동 처리
    #    - ServiceResult.fail: 예기치 않은 내부 오류 → 500 반환
    service = WeeklyReportService()
    result = await service.execute(service_input)

    if result.success:
        return result.data  # type: ignore[return-value]

    raise HTTPException(
        status_code=500,
        detail=f"주간보고 생성 중 오류가 발생했습니다: {result.error}",
    )

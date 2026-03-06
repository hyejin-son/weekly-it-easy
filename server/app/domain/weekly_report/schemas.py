"""
weekly_report 도메인 요청/응답 스키마 정의

FastAPI multipart/form-data 엔드포인트에서 사용할 데이터 계약을 정의한다.
- WeeklyReportRequest: 엔드포인트 파라미터 명세 (dataclass 형태의 문서화 용도)
- WeeklyReportResponse: Pydantic 응답 모델
- WeeklyReportRecord: Extract API 응답 단위 레코드 (Task 4-1)
- ExtractResponse: POST /extract 응답 스키마 (Task 4-1)
- GenerateRequest: POST /generate JSON body 스키마 (Task 4-1, Task 4-2에서 사용)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel


@dataclass
class WeeklyReportRequest:
    """
    POST /api/v1/weekly-report/generate 요청 파라미터 명세

    실제 FastAPI 엔드포인트에서는 Form() + File() 의존성을 함수 시그니처에
    직접 선언하여 사용한다 (Task 2-2에서 구현).
    이 클래스는 요청 파라미터의 데이터 계약을 문서화하는 역할을 한다.
    """

    report_date: str
    file_ab_1: UploadFile
    file_ab_2: UploadFile
    file_cd_1: UploadFile
    file_cd_2: UploadFile


class WeeklyReportResponse(BaseModel):
    """
    POST /api/v1/weekly-report/generate 응답 스키마

    Attributes:
        result_text: 포맷팅된 주간보고 텍스트 (복사 가능한 최종 결과물)
    """

    result_text: str


# ====================
# Task 4-1: 2-Step 아키텍처용 스키마
# ====================


class WeeklyReportRecord(BaseModel):
    """
    Extract API 응답의 단위 레코드 (Gemini 윤문 없는 원본 데이터).

    Attributes:
        request_id:   A열 — 요청 ID
        company:      J열 — 요청회사 (창원/베스틸 분류 기준)
        biz_system:   F열 — 업무시스템1
        biz_system2:  W열 — 업무시스템2 (e-Procurement 필터링 기준값 포함)
        category:     구분 (개발/개선 or 프로젝트/운영)
        status:       진행상태 (완료 / 대기 / 진행중)
        schedule:     ~mm/dd 포맷, 없으면 빈 문자열
        title_raw:    G열 제목 원본
        summary_raw:  H열 요구사항 원본
        content_raw:  R열 또는 AB열 처리내용 원본 (없으면 None)
    """

    request_id: str
    company: str
    biz_system: str
    biz_system2: str
    category: str
    status: str
    schedule: str
    title_raw: str
    summary_raw: str
    content_raw: Optional[str]


class ExtractResponse(BaseModel):
    """
    POST /api/v1/weekly-report/extract 응답 스키마

    Attributes:
        records: 파싱·필터링된 주간보고 레코드 목록 (Gemini 윤문 없는 원본)
    """

    records: list[WeeklyReportRecord]


class GenerateRequest(BaseModel):
    """
    POST /api/v1/weekly-report/generate JSON body 스키마 (Task 4-2에서 사용 예정).

    Extract 단계에서 얻은 레코드 목록을 그대로 전달하여 Gemini 윤문 + 포맷팅을 수행한다.

    Attributes:
        report_date: 보고 기준 날짜 (ISO 형식: YYYY-MM-DD)
        records:     ExtractResponse.records에서 받은 레코드 목록
    """

    report_date: str
    records: list[WeeklyReportRecord]

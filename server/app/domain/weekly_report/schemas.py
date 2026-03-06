"""
weekly_report 도메인 요청/응답 스키마 정의

FastAPI multipart/form-data 엔드포인트에서 사용할 데이터 계약을 정의한다.
- WeeklyReportRequest: 엔드포인트 파라미터 명세 (dataclass 형태의 문서화 용도)
- WeeklyReportResponse: Pydantic 응답 모델
"""

from dataclasses import dataclass

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

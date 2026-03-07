"""
WeeklyReportCalculator: Excel 파싱 + 데이터 필터링·매핑 + Gemini 윤문

Task 1-1 구현 범위:
    - 로직 1: AB/CD 파일 통합 (pd.concat)
    - 로직 2: e-Procurement 필터 + 날짜 범위 필터
    - 로직 3: 요청 ID / 진행상태 / 일정 / 구분 매핑
    - 로직 4: 제목 / 요구사항 / 처리내용 원본 텍스트 추출

Task 1-2 구현 범위:
    - 로직 5: Gemini API 비동기 윤문 (Batch 방식, Rate Limit 방어)
              - 최대 2회 Retry + 지수 백오프
              - 실패 시 원본 텍스트 Fallback
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from pydantic import BaseModel

from server.app.shared.base.calculator import BaseCalculator
from server.app.shared.types import CalculatorInput, CalculatorOutput
from server.app.core.config import settings
from server.app.domain.weekly_report.schemas import WeeklyReportRecord

logger = logging.getLogger(__name__)

# ====================
# 컬럼 인덱스 상수 (0-indexed, Excel 열 알파벳 → 위치)
# A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9
# O=14, P=15, Q=16, R=17, S=18, T=19
# W=22, Z=25, AB=27
# ====================

COL_A = 0   # 요청 ID
COL_B = 1   # 단계(진행상태)
COL_C = 2   # 구분 (T열 없을 때 사용)
COL_D = 3   # 구분상세 (CD 파일 lookup 대상)
COL_F = 5   # 업무시스템1
COL_G = 6   # 제목
COL_H = 7   # 요구사항
COL_J = 9   # 요청회사 (창원/베스틸 분류 기준)
COL_O = 14  # 일정 대안 (P열 없을 때 사용)
COL_P = 15  # 처리완료일 (T열 없을 때 날짜 기준)
COL_R = 17  # 처리내용 (T열 없을 때)
COL_T = 19  # 변경 ID (결측 여부로 일반/변경 건 분기)
COL_W = 22  # 업무시스템2
COL_Z = 25  # 변경건 처리완료일 (T열 있을 때 날짜 기준)
COL_AB = 27 # 변경건 처리내용 (T열 있을 때)

# 필수 컬럼 수: AB열(index 27)을 사용하므로 최소 28개 컬럼 필요
MIN_REQUIRED_COLS = 28
# CD 파일(CH 변경관리 이력) 필수 컬럼 수: D열(index 3) lookup만 사용하므로 14개로 충분
MIN_REQUIRED_COLS_CD = 14

# ====================
# 비즈니스 규칙 상수
# ====================

EPRO_VALUES: frozenset[str] = frozenset({
    "세아베스틸>기타>e-Procurement",
    "세아창원특수강>기타>e-Procurement",
})

STATUS_DONE: frozenset[str] = frozenset({"종료", "중단종료", "취소종료"})
STATUS_WAIT: frozenset[str] = frozenset({"요청 접수 및 분류"})

CATEGORY_DEV_VALUE = "서비스요청 > 전산개발수정/신규 요청"
CATEGORY_DEV = "개발/개선"
CATEGORY_OPS = "프로젝트/운영"


# ====================
# Input / Output 모델
# ====================


class WeeklyReportCalculatorInput(CalculatorInput):
    """
    WeeklyReportCalculator 입력 모델.

    Service 레이어에서 UploadFile.read()로 읽은 bytes를 전달한다.
    """

    report_date: str  # ISO 형식: "YYYY-MM-DD" (해당 주 포함 날짜면 무관)
    file_ab_1: bytes
    file_ab_2: bytes
    file_cd_1: bytes
    file_cd_2: bytes


class ProcessedRecord(BaseModel):
    """
    로직 3+4 매핑 결과 단위 레코드.

    Task 1-2에서 Gemini가 title/requirements/processing_content를 윤문하여
    refined_title / refined_overview / refined_content에 저장한다.
    Gemini 미사용 또는 실패 시 refined 필드는 None으로 유지된다.
    """

    request_id: str
    status: str             # '완료' | '대기' | '진행중'
    schedule: Optional[str]  # '~MM/DD' 형식, 없으면 None
    category: str
    company: str            # J열 값 그대로 (Formatter에서 창원/베스틸 분류)
    title: str              # G열 원본
    requirements: str       # H열 원본
    processing_content: Optional[str]  # R열 또는 AB열 원본, 없으면 None

    # Gemini 윤문 결과 (Task 1-2)
    refined_title: Optional[str] = None     # Gemini [제목] 결과
    refined_overview: Optional[str] = None  # Gemini [개요] 결과
    refined_content: Optional[str] = None   # Gemini [내용] 결과


class WeeklyReportCalculatorOutput(CalculatorOutput):
    """WeeklyReportCalculator 출력 모델."""

    records: list[ProcessedRecord]


# ====================
# Calculator 구현
# ====================


class WeeklyReportCalculator(
    BaseCalculator[WeeklyReportCalculatorInput, WeeklyReportCalculatorOutput]
):
    """
    Excel 파싱 + 데이터 필터링·매핑 + Gemini 윤문 Calculator (Task 1-1 + 1-2)

    호출 순서:
        calculate()
            └─ _consolidate_files()      # 로직 1: 파일 통합
            └─ _get_week_range()         # 날짜 범위 계산
            └─ _filter_rows()            # 로직 2: 필터링
            └─ _map_records()            # 로직 3+4: 매핑 + 텍스트 추출
            └─ _refine_records_batch()   # 로직 5: Gemini 윤문 (모델 있을 때만)
    """

    def __init__(self) -> None:
        self._gemini_model = self._init_gemini()

    def _init_gemini(self):
        """
        Gemini 모델을 초기화하여 반환한다.

        google.generativeai를 lazy import하여 패키지 미설치 환경에서도
        Task 1-1 로직이 정상 동작하도록 한다.
        GEMINI_API_KEY가 없거나 초기화 실패 시 None을 반환한다.
        """
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.warning("GEMINI_API_KEY가 설정되지 않아 Gemini 윤문을 건너뜁니다.")
            return None
        try:
            import google.generativeai as genai  # noqa: PLC0415
            genai.configure(api_key=api_key)
            return genai.GenerativeModel("gemini-1.5-flash")
        except Exception as e:
            logger.error(f"Gemini 모델 초기화 실패: {e}")
            return None

    async def calculate(
        self, input_data: WeeklyReportCalculatorInput
    ) -> WeeklyReportCalculatorOutput:
        """
        Excel 4개 파일을 읽어 필터링·매핑된 레코드 리스트를 반환한다.

        Args:
            input_data: 파일 bytes 4개 + report_date

        Returns:
            WeeklyReportCalculatorOutput: 처리된 레코드 리스트

        Raises:
            ValueError: 컬럼 수가 부족하거나 날짜 형식이 잘못된 경우
        """
        # 날짜 범위 계산 (빠른 검증, I/O 없음)
        monday, friday = self._get_week_range(input_data.report_date)

        # 로직 1: 파일 통합
        df_ab, df_cd = self._consolidate_files(input_data)

        # 컬럼 수 검증
        self._validate_min_columns(df_ab, "AB", MIN_REQUIRED_COLS)
        self._validate_min_columns(df_cd, "CD", MIN_REQUIRED_COLS_CD)

        # 로직 2: 필터링 (AB 파일만 대상)
        df_filtered = self._filter_rows(df_ab, monday, friday)

        # 로직 3+4: 매핑 (CD는 lookup 전용)
        records = self._map_records(df_filtered, df_cd)

        # 로직 5: Gemini 비동기 윤문 (모델이 없거나 레코드가 없으면 건너뜀)
        if self._gemini_model and records:
            records = await self._refine_records_batch(records)

        return WeeklyReportCalculatorOutput(records=records)

    async def refine(
        self, records: list[WeeklyReportRecord]
    ) -> list[ProcessedRecord]:
        """
        WeeklyReportRecord 리스트를 Gemini로 윤문하여 ProcessedRecord 리스트를 반환한다 (Task 4-2).

        파일 파싱(Excel) 코드 없음. Batch API 호출 및 Retry 로직만 수행한다.
        GEMINI_API_KEY가 없거나 모델 초기화 실패 시 원본 텍스트가 유지된다.

        Args:
            records: /extract 단계에서 얻은 WeeklyReportRecord 리스트

        Returns:
            list[ProcessedRecord]: Gemini 윤문 결과(refined_* 필드 채워짐)를 포함한 레코드 리스트
        """
        processed = [self._weekly_record_to_processed(r) for r in records]

        if self._gemini_model and processed:
            processed = await self._refine_records_batch(processed)

        return processed

    def _weekly_record_to_processed(self, record: WeeklyReportRecord) -> ProcessedRecord:
        """
        WeeklyReportRecord를 ProcessedRecord로 변환한다 (Task 4-2).

        필드 매핑:
            title_raw     → title
            summary_raw   → requirements
            content_raw   → processing_content
            schedule (빈 문자열) → None
            나머지 필드는 직접 매핑
        """
        return ProcessedRecord(
            request_id=record.request_id,
            status=record.status,
            schedule=record.schedule if record.schedule else None,
            category=record.category,
            company=record.company,
            title=record.title_raw,
            requirements=record.summary_raw,
            processing_content=record.content_raw,
        )

    async def extract(
        self, input_data: WeeklyReportCalculatorInput
    ) -> list[WeeklyReportRecord]:
        """
        Excel 파싱 → 필터링 → WeeklyReportRecord 리스트 반환 (Task 4-1).

        Gemini 윤문(_refine_records_batch)을 호출하지 않아 즉시 응답이 가능하다.
        기존 calculate()의 로직 1~4 전처리만 수행한다.

        Args:
            input_data: 파일 bytes 4개 + report_date

        Returns:
            list[WeeklyReportRecord]: 파싱·필터링된 레코드 목록 (원본 텍스트)
        """
        monday, friday = self._get_week_range(input_data.report_date)
        df_ab, df_cd = self._consolidate_files(input_data)
        self._validate_min_columns(df_ab, "AB", MIN_REQUIRED_COLS)
        self._validate_min_columns(df_cd, "CD", MIN_REQUIRED_COLS_CD)
        df_filtered = self._filter_rows(df_ab, monday, friday)
        return self._map_rows_to_weekly_records(df_filtered, df_cd)

    def _map_rows_to_weekly_records(
        self, df: pd.DataFrame, df_cd: pd.DataFrame
    ) -> list[WeeklyReportRecord]:
        """
        필터링된 DataFrame을 WeeklyReportRecord 리스트로 변환한다 (Task 4-1).

        기존 _map_records()와 달리 biz_system, biz_system2 필드를 포함하며
        WeeklyReportRecord 스키마에 맞게 반환한다. Gemini 로직 없음.
        """
        records: list[WeeklyReportRecord] = []
        for _, row in df.iterrows():
            records.append(self._map_single_row_to_weekly_record(row, df_cd))
        return records

    def _map_single_row_to_weekly_record(
        self, row: pd.Series, df_cd: pd.DataFrame
    ) -> WeeklyReportRecord:
        """단일 행을 WeeklyReportRecord로 변환한다 (Task 4-1)."""
        request_id = self._to_str(row.iloc[COL_A])
        schedule_opt = self._get_schedule(row)

        return WeeklyReportRecord(
            request_id=request_id,
            company=self._to_str(row.iloc[COL_J]),
            biz_system=self._to_str(row.iloc[COL_F]),
            biz_system2=self._to_str(row.iloc[COL_W]),
            category=self._get_category(row, df_cd, request_id),
            status=self._get_status(row.iloc[COL_B]),
            schedule=schedule_opt if schedule_opt is not None else "",
            title_raw=self._to_str(row.iloc[COL_G]),
            summary_raw=self._to_str(row.iloc[COL_H]),
            content_raw=self._get_content_raw(row),
        )

    def _get_content_raw(self, row: pd.Series) -> Optional[str]:
        """
        T열 결측 여부에 따라 처리내용 원본 텍스트를 반환한다 (Task 4-1).

        T열 NaN → P열에 값 있으면 R열, 없으면 None
        T열 있음 → Z열에 값 있으면 AB열, 없으면 None
        """
        has_t = not pd.isna(row.iloc[COL_T])
        if not has_t:
            p_val = row.iloc[COL_P]
            return self._to_str_or_none(row.iloc[COL_R]) if not pd.isna(p_val) else None
        else:
            z_val = row.iloc[COL_Z]
            return self._to_str_or_none(row.iloc[COL_AB]) if not pd.isna(z_val) else None

    # --------------------------------------------------
    # 로직 1: 파일 통합
    # --------------------------------------------------

    def _consolidate_files(
        self, input_data: WeeklyReportCalculatorInput
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        AB 파일 2개, CD 파일 2개를 각각 concat한다.

        - header=2: 0-indexed이므로 3번째 행을 헤더로 읽음
        - ignore_index=True: 연속 인덱스 보장
        """
        df_ab = pd.concat(
            [
                pd.read_excel(io.BytesIO(input_data.file_ab_1), header=2),
                pd.read_excel(io.BytesIO(input_data.file_ab_2), header=2),
            ],
            ignore_index=True,
        )
        df_cd = pd.concat(
            [
                pd.read_excel(io.BytesIO(input_data.file_cd_1), header=2),
                pd.read_excel(io.BytesIO(input_data.file_cd_2), header=2),
            ],
            ignore_index=True,
        )
        return df_ab, df_cd

    # --------------------------------------------------
    # 날짜 범위 헬퍼
    # --------------------------------------------------

    def _get_week_range(self, report_date_str: str) -> tuple[date, date]:
        """
        report_date_str이 속한 주의 월요일~금요일을 반환한다.

        Args:
            report_date_str: "YYYY-MM-DD" 형식

        Returns:
            (monday, friday) as date objects

        Raises:
            ValueError: 날짜 형식이 잘못된 경우
        """
        try:
            ref = date.fromisoformat(report_date_str)
        except ValueError:
            raise ValueError(
                f"report_date 형식이 올바르지 않습니다: '{report_date_str}' "
                "(올바른 형식: YYYY-MM-DD)"
            )
        monday = ref - timedelta(days=ref.weekday())  # weekday(): 월=0, 일=6
        friday = monday + timedelta(days=4)
        return monday, friday

    # --------------------------------------------------
    # 로직 2: 필터링
    # --------------------------------------------------

    def _filter_rows(
        self, df: pd.DataFrame, monday: date, friday: date
    ) -> pd.DataFrame:
        """
        e-Procurement 필터 + 날짜 범위 필터를 적용한다.

        e-Procurement 필터:
            F열(COL_F) 또는 W열(COL_W) 값이 EPRO_VALUES에 포함된 행만 추출

        날짜 필터:
            행별로 T열(COL_T) 결측 여부에 따라 날짜 기준 열 분기:
                - T열 NaN → P열(COL_P) 기준
                - T열 있음 → Z열(COL_Z) 기준
            날짜 기준 열이 NaN이면 무조건 포함 (진행중/대기 건)
            날짜 기준 열이 있으면 monday <= 날짜 <= friday 이면 포함
        """
        # e-Procurement 필터 (OR 조건)
        col_f = df.iloc[:, COL_F]
        col_w = df.iloc[:, COL_W]
        mask_epro = col_f.isin(EPRO_VALUES) | col_w.isin(EPRO_VALUES)
        df_epro = df[mask_epro].copy()

        if df_epro.empty:
            return df_epro

        # 날짜 범위 필터 (행별 적용)
        mask_date = df_epro.apply(
            lambda row: self._is_in_date_range(row, monday, friday), axis=1
        )
        return df_epro[mask_date].reset_index(drop=True)

    def _is_in_date_range(self, row: pd.Series, monday: date, friday: date) -> bool:
        """
        단일 행의 날짜가 해당 주 범위에 포함되는지 판단한다.

        T열 NaN → P열 기준, T열 있음 → Z열 기준.
        날짜 기준 열이 NaN이면 True (진행중/대기 건은 항상 포함).
        """
        has_t = not pd.isna(row.iloc[COL_T])
        date_col_idx = COL_Z if has_t else COL_P
        date_val = row.iloc[date_col_idx]

        if pd.isna(date_val):
            return True  # 날짜 없음 → 진행중/대기로 간주, 항상 포함

        try:
            row_date = pd.to_datetime(date_val).date()
            return monday <= row_date <= friday
        except Exception:
            return True  # 날짜 파싱 실패도 안전하게 포함

    # --------------------------------------------------
    # 로직 3+4: 매핑 + 원본 텍스트 추출
    # --------------------------------------------------

    def _map_records(
        self, df: pd.DataFrame, df_cd: pd.DataFrame
    ) -> list[ProcessedRecord]:
        """
        필터링된 DataFrame을 ProcessedRecord 리스트로 변환한다.

        df_cd는 T열이 있는 행의 구분(D열) 조회에만 사용된다.
        """
        records: list[ProcessedRecord] = []
        for _, row in df.iterrows():
            records.append(self._map_single_row(row, df_cd))
        return records

    def _map_single_row(
        self, row: pd.Series, df_cd: pd.DataFrame
    ) -> ProcessedRecord:
        """단일 행을 ProcessedRecord로 변환한다."""
        request_id = self._to_str(row.iloc[COL_A])
        status = self._get_status(row.iloc[COL_B])
        schedule = self._get_schedule(row)
        category = self._get_category(row, df_cd, request_id)
        company = self._to_str(row.iloc[COL_J])
        title, requirements, processing_content = self._get_texts(row)

        return ProcessedRecord(
            request_id=request_id,
            status=status,
            schedule=schedule,
            category=category,
            company=company,
            title=title,
            requirements=requirements,
            processing_content=processing_content,
        )

    # --------------------------------------------------
    # 로직 3 헬퍼: 진행상태 매핑
    # --------------------------------------------------

    def _get_status(self, b_value: object) -> str:
        """
        B열 값을 진행상태 문자열로 변환한다.

        '종료' / '중단종료' / '취소종료' → '완료'
        '요청 접수 및 분류'              → '대기'
        그 외                            → '진행중'
        """
        if pd.isna(b_value):
            return "진행중"
        val = str(b_value).strip()
        if val in STATUS_DONE:
            return "완료"
        if val in STATUS_WAIT:
            return "대기"
        return "진행중"

    # --------------------------------------------------
    # 로직 3 헬퍼: 일정 매핑
    # --------------------------------------------------

    def _get_schedule(self, row: pd.Series) -> Optional[str]:
        """
        P열(COL_P) 값을 우선 사용, 없으면 O열(COL_O) 사용.
        존재하면 '~MM/DD' 형식으로 반환, 없으면 None.
        """
        p_val = row.iloc[COL_P]
        o_val = row.iloc[COL_O]

        date_val = p_val if not pd.isna(p_val) else o_val
        if pd.isna(date_val):
            return None

        try:
            d = pd.to_datetime(date_val)
            return f"~{d.month:02d}/{d.day:02d}"
        except Exception:
            return None

    # --------------------------------------------------
    # 로직 3 헬퍼: 구분 매핑
    # --------------------------------------------------

    def _get_category(
        self, row: pd.Series, df_cd: pd.DataFrame, request_id: str
    ) -> str:
        """
        T열 결측 여부에 따라 구분을 결정한다.

        T열 NaN → C열(COL_C) 값 그대로 반환
        T열 있음 → df_cd에서 A열 == request_id 인 행 찾기
                   D열 값이 CATEGORY_DEV_VALUE이면 '개발/개선'
                   그 외 또는 미발견이면 '프로젝트/운영'
        """
        has_t = not pd.isna(row.iloc[COL_T])

        if not has_t:
            return self._to_str(row.iloc[COL_C])

        # CD 파일 lookup
        if df_cd.empty:
            return CATEGORY_OPS

        cd_a_col = df_cd.iloc[:, COL_A]
        matched = df_cd[cd_a_col == request_id]
        if matched.empty:
            return CATEGORY_OPS

        d_val = matched.iloc[0].iloc[COL_D]
        if not pd.isna(d_val) and str(d_val).strip() == CATEGORY_DEV_VALUE:
            return CATEGORY_DEV
        return CATEGORY_OPS

    # --------------------------------------------------
    # 로직 4 헬퍼: 원본 텍스트 추출
    # --------------------------------------------------

    def _get_texts(
        self, row: pd.Series
    ) -> tuple[str, str, Optional[str]]:
        """
        T열 결측 여부에 따라 텍스트 추출 열을 분기한다.

        T열 NaN:
            title         = G열
            requirements  = H열
            processing_content = R열 (P열에 값이 있을 때만, 없으면 None)

        T열 있음:
            title         = G열
            requirements  = H열
            processing_content = AB열 (Z열에 값이 있을 때만, 없으면 None)

        Returns:
            (title, requirements, processing_content)
        """
        has_t = not pd.isna(row.iloc[COL_T])

        title = self._to_str(row.iloc[COL_G])
        requirements = self._to_str(row.iloc[COL_H])

        if not has_t:
            p_val = row.iloc[COL_P]
            processing_content = (
                self._to_str_or_none(row.iloc[COL_R])
                if not pd.isna(p_val)
                else None
            )
        else:
            z_val = row.iloc[COL_Z]
            processing_content = (
                self._to_str_or_none(row.iloc[COL_AB])
                if not pd.isna(z_val)
                else None
            )

        return title, requirements, processing_content

    # --------------------------------------------------
    # 로직 5: Gemini 비동기 윤문 (Batch 방식)
    # --------------------------------------------------

    async def _refine_records_batch(
        self, records: list[ProcessedRecord]
    ) -> list[ProcessedRecord]:
        """
        모든 레코드를 단일 Gemini API 호출로 일괄 윤문한다 (Batch 방식).

        Rate Limit 방어: 레코드 수에 무관하게 API 호출 1회로 처리.
        실패 또는 파싱 오류 시 원본 텍스트를 유지한다.
        """
        input_data = [
            {
                "id": i,
                "title": r.title,
                "requirements": r.requirements,
                "processing_content": r.processing_content or "",
            }
            for i, r in enumerate(records)
        ]
        prompt = self._build_batch_prompt(input_data)
        response_text = await self._call_gemini_with_retry(prompt)

        if response_text is None:
            logger.error("Gemini API 최종 실패. 전체 레코드 원본 텍스트를 유지합니다.")
            return records

        refined_list = self._parse_batch_response(response_text)
        if refined_list is None:
            logger.error("Gemini 응답 파싱 실패. 전체 레코드 원본 텍스트를 유지합니다.")
            return records

        # id 기준 lookup dict 구성
        refined_map: dict[int, dict] = {item["id"]: item for item in refined_list if "id" in item}

        result: list[ProcessedRecord] = []
        for i, record in enumerate(records):
            item = refined_map.get(i)
            if item:
                result.append(
                    record.model_copy(
                        update={
                            "refined_title": item.get("refined_title") or None,
                            "refined_overview": item.get("refined_overview") or None,
                            "refined_content": item.get("refined_content") or None,
                        }
                    )
                )
            else:
                result.append(record)
        return result

    def _build_batch_prompt(self, input_data: list[dict]) -> str:
        """
        일괄 윤문을 위한 Gemini 프롬프트를 구성한다.

        출력 형식: id별 [제목], [개요], [내용]을 담은 JSON 배열.
        """
        items_json = json.dumps(input_data, ensure_ascii=False, indent=2)
        return (
            "다음은 IT 서비스 데스크 업무 항목 목록입니다. "
            "각 항목을 주간보고서에 어울리도록 윤문해 주세요.\n\n"
            "규칙:\n"
            "- [제목]: 핵심만 담아 1줄로 작성\n"
            "- [개요]: 요구사항을 1~2줄로 요약 (비즈니스 용어 사용)\n"
            "- [내용]: 처리내용이 있으면 1~2줄로 요약, 없으면 빈 문자열\n"
            "- 인사말, 이름, 불필요한 수식어 제거\n\n"
            f"입력 데이터 (JSON):\n{items_json}\n\n"
            "출력 형식 — 아래 JSON 배열만 출력하고 다른 텍스트는 포함하지 마세요:\n"
            "[\n"
            '  {"id": 0, "refined_title": "...", "refined_overview": "...", "refined_content": "..."},\n'
            "  ...\n"
            "]"
        )

    async def _call_gemini_with_retry(
        self, prompt: str, max_retries: int = 2
    ) -> Optional[str]:
        """
        Gemini API를 호출하고 실패 시 최대 max_retries회 재시도한다.

        지수 백오프: 1회 실패 후 1초, 2회 실패 후 2초 대기.
        모든 재시도 소진 후에도 실패하면 None을 반환한다.
        """
        for attempt in range(max_retries + 1):
            try:
                response = await self._gemini_model.generate_content_async(prompt)
                return response.text
            except Exception as e:
                if attempt < max_retries:
                    wait_seconds = 2 ** attempt  # 1초, 2초
                    logger.warning(
                        f"Gemini API 호출 실패 (시도 {attempt + 1}/{max_retries + 1}): {e}. "
                        f"{wait_seconds}초 후 재시도합니다."
                    )
                    await asyncio.sleep(wait_seconds)
                else:
                    logger.error(
                        f"Gemini API 최종 실패 (시도 {attempt + 1}/{max_retries + 1}): {e}"
                    )
        return None

    def _parse_batch_response(self, response_text: str) -> Optional[list[dict]]:
        """
        Gemini 배치 응답 텍스트를 파싱하여 dict 리스트로 반환한다.

        JSON 코드 블록(```json ... ```) 래퍼를 자동으로 제거한다.
        파싱 실패 시 None을 반환한다.
        """
        try:
            text = response_text.strip()
            # JSON 코드 블록 래퍼 제거
            if text.startswith("```"):
                lines = text.splitlines()
                # 첫 줄(```json 또는 ```) 및 마지막 줄(```) 제거
                inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                text = "\n".join(inner).strip()

            parsed = json.loads(text)
            if not isinstance(parsed, list):
                logger.error(f"Gemini 응답이 배열이 아닙니다: {type(parsed)}")
                return None
            return parsed
        except Exception as e:
            logger.error(f"Gemini 응답 JSON 파싱 실패: {e}. 응답 텍스트: {response_text[:200]}")
            return None

    # --------------------------------------------------
    # 공통 유틸리티
    # --------------------------------------------------

    @staticmethod
    def _to_str(value: object) -> str:
        """NaN이면 빈 문자열, 아니면 strip된 문자열로 변환."""
        if pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _to_str_or_none(value: object) -> Optional[str]:
        """NaN이면 None, 아니면 strip된 문자열로 변환. 빈 문자열도 None 처리."""
        if pd.isna(value):
            return None
        stripped = str(value).strip()
        return stripped if stripped else None

    @staticmethod
    def _validate_min_columns(df: pd.DataFrame, label: str, min_cols: int) -> None:
        """
        DataFrame이 min_cols 이상의 컬럼을 보유하는지 검증한다.

        Raises:
            ValueError: 컬럼 수가 부족한 경우
        """
        if len(df.columns) < min_cols:
            raise ValueError(
                f"{label} 파일의 컬럼 수가 부족합니다. "
                f"최소 {min_cols}개 필요, 현재 {len(df.columns)}개. "
                "올바른 양식의 Excel 파일을 업로드해 주세요."
            )

"""
WeeklyReportCalculator: Excel 파싱 + 데이터 필터링·매핑

Task 1-1 구현 범위:
    - 로직 1: AB/CD 파일 통합 (pd.concat)
    - 로직 2: e-Procurement 필터 + 날짜 범위 필터
    - 로직 3: 요청 ID / 진행상태 / 일정 / 구분 매핑
    - 로직 4: 제목 / 요구사항 / 처리내용 원본 텍스트 추출

Task 1-2(Gemini 연동)는 이 파일을 수정하여 추가된다.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from pydantic import BaseModel

from server.app.shared.base.calculator import BaseCalculator
from server.app.shared.types import CalculatorInput, CalculatorOutput

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

    Task 1-2에서 Gemini가 title/requirements/processing_content를 윤문한다.
    """

    request_id: str
    status: str             # '완료' | '대기' | '진행중'
    schedule: Optional[str]  # '~MM/DD' 형식, 없으면 None
    category: str
    company: str            # J열 값 그대로 (Formatter에서 창원/베스틸 분류)
    title: str              # G열 원본
    requirements: str       # H열 원본
    processing_content: Optional[str]  # R열 또는 AB열 원본, 없으면 None


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
    Excel 파싱 + 데이터 필터링·매핑 Calculator (Task 1-1)

    호출 순서:
        calculate()
            └─ _consolidate_files()   # 로직 1: 파일 통합
            └─ _get_week_range()      # 날짜 범위 계산
            └─ _filter_rows()         # 로직 2: 필터링
            └─ _map_records()         # 로직 3+4: 매핑 + 텍스트 추출
    """

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
        self._validate_min_columns(df_ab, "AB")
        self._validate_min_columns(df_cd, "CD")

        # 로직 2: 필터링 (AB 파일만 대상)
        df_filtered = self._filter_rows(df_ab, monday, friday)

        # 로직 3+4: 매핑 (CD는 lookup 전용)
        records = self._map_records(df_filtered, df_cd)

        return WeeklyReportCalculatorOutput(records=records)

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
    def _validate_min_columns(df: pd.DataFrame, label: str) -> None:
        """
        DataFrame이 MIN_REQUIRED_COLS(28) 이상의 컬럼을 보유하는지 검증한다.

        Raises:
            ValueError: 컬럼 수가 부족한 경우
        """
        if len(df.columns) < MIN_REQUIRED_COLS:
            raise ValueError(
                f"{label} 파일의 컬럼 수가 부족합니다. "
                f"최소 {MIN_REQUIRED_COLS}개 필요, 현재 {len(df.columns)}개. "
                "올바른 양식의 Excel 파일을 업로드해 주세요."
            )

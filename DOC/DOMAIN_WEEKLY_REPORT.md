# 프로젝트: 주간보고 자동화 도메인 추가 (FastAPI + React)

## 1. 개요
사용자가 업로드한 4개의 ITS/어플리케이션 변경관리 엑셀 파일을 분석하여 주간보고 양식을 생성하고, **그 결과를 프론트엔드 화면에 텍스트로 출력하여 사용자가 복사(Copy)할 수 있도록 제공**하는 기능을 추가한다. 
**이 기능은 프로젝트의 `ARCHITECTURE.md` 및 `DEVELOPMENT_GUIDE.md`를 엄격히 준수하는 새로운 도메인(`weekly_report`)으로 구현되어야 한다.**

## 2. 기술 스택 및 아키텍처 원칙
- **Backend**: Python 3.12, FastAPI, Pydantic 
- **Frontend**: React 19, TypeScript, Zustand 
- **AI Integration**: `google-generativeai` (Gemini API)
- **디자인 패턴**: 계층화된 아키텍처 (`Router` -> `Service` -> `Calculator` / `Formatter`)
- **제외 사항**: 본 도메인은 DB나 외부 Google Sheets API와 통신하지 않으므로 `Repository` 계층은 생략하거나 Mocking 처리한다.

## 3. 백엔드 도메인 설계 (Layer별 역할)

### 3.1. Router Layer (`router.py`)
- **역할:** 프론트엔드로부터 주간 보고 날짜와 4개의 엑셀 파일(**AB 파일 2개, CD 파일 2개로 명시적 구분**)을 `UploadFile`로 수신. 완료된 최종 포맷팅 텍스트(String)를 프론트엔드로 반환.
- **파일 비즈니스 의미:**
  - **AB 파일** (2개): 베스틸 + 창원의 **ITS 서비스 및 변경 실적 데이터 (SR+CH 통합)** — 메인 분석 대상
  - **CD 파일** (2개): 베스틸 + 창원의 **어플리케이션 변경관리 이력 데이터 (CH 참고용)** — AB 파일의 T열(변경 ID) 조인용
  - **⚠ 주의:** AB/CD 구분은 데이터 성격(ITS vs CH) 기준이며, 창원/베스틸 분류는 각 파일 내 **J열(요청회사)** 값으로만 결정됨

### 3.2. Calculator Layer (`calculator.py`)
- **역할:** 비즈니스 로직 계산, Pandas 데이터 전처리 및 필터링, Gemini API 텍스트 윤문.
- **로직 1 (통합):** A+B 병합(`AB 파일`), C+D 병합(`CD 파일`). Header는 3행(`header=2`).
- **로직 2 (필터링 기준 - 모든 기준은 SR 데이터):**
  - **추출 대상:** `AB 파일`의 F열 또는 W열(업무시스템2)이 '세아베스틸>기타>e-Procurement' 또는 '세아창원특수강>기타>e-Procurement'인 건.
  - **날짜 필터링:** T열(변경 ID)이 없으면 P열(처리완료일) 기준, 있으면 Z열 기준.
    - 해당 날짜가 사용자가 입력한 날짜의 주(월~금)에 포함되면 추출. 빈 값이면(진행/대기) 무조건 추출.
- **로직 3 (기본 데이터 매핑):**
  - 요청 ID: A열
  - 진행상태: B열 기준 ('종료/중단종료/취소종료' -> 완료, '요청 접수 및 분류' -> 대기, 그 외 -> 진행중)
  - 일정(~mm/dd): P열 추출(없으면 O열). `MM/DD` 포맷.
  - 구분: T열 없으면 C열, T열 있으면 `CD 파일`과 조인하여 D열 확인. '서비스요청 > 전산개발수정/신규 요청'이면 `개발/개선`, 그 외 `프로젝트/운영`.
- **로직 4 (제목, 개요, 내용 원본 추출 및 Gemini 윤문):** - **원본 텍스트 추출 우선순위 규칙:**
    - T열(변경 ID)이 없는 건: G열(제목), H열(요구사항) 추출. 만약 P열(처리완료일)에 데이터가 있으면 R열(처리내용) 추가 추출.
    - T열(변경 ID)이 있는 건: G열(제목), H열(요구사항) 추출. 만약 Z열(처리완료일)에 데이터가 있으면 AB열(처리내용) 추가 추출.
  - **AI 윤문 (`google-generativeai` 비동기 호출):**
    - 위에서 추출한 원본 텍스트를 프롬프트로 전달하여 "주간보고서의 [제목], [개요], [내용] 항목에 맞게 각각 1~2줄 이내의 명확한 비즈니스 용어로 요약. 인사말, 이름 제거." 하도록 지시.
    - **(추가) 병목/Rate Limit 방지:** 개별 건 호출 시 `asyncio.Semaphore`를 활용해 동시 호출 수를 제어하거나, 다건의 데이터를 JSON 배열 형태의 프롬프트로 묶어 Batch 처리하는 방식을 적용하여 API 과부하 방지.

### 3.3. Formatter Layer (`formatter.py`)
- **역할:** Calculator에서 정제된 데이터를 최종 화면에 뿌려줄 텍스트로 포맷팅.
- **포맷팅 규칙:** J열(요청회사)을 기준으로 창원/베스틸 분류하여 아래 텍스트 문자열 생성. (처리내용이 없으면 생략)

```text
◈EPRO 운영
[창원]
▣ ({구분}) ({요청 ID}) {제목} (~{mm/dd}, {진행상태})
  -. 개요 : {개요}
  -. 내용 : {내용}

[베스틸]
▣ ({구분}) ({요청 ID}) {제목} (~{mm/dd}, {진행상태})
  -. 개요 : {개요}
  -. 내용 : {내용}
```

### 3.4. Service Layer (`service.py`)
- **역할:** Router의 요청을 받아 `Calculator`, `Formatter` 클래스들을 주입받아 워크플로우를 조율하고 최종 문자열을 반환.
- **(추가) 데이터 검증:** 전달받은 파일이 정상적인 엑셀인지, 필수 컬럼이 존재하는지 사전 검증하고 오류 시 명확한 예외 발생.

## 4. 프론트엔드 설계
- **UI:** 1. 날짜 선택(DatePicker).
  2. **(추가) 파일 업로드 영역 분리:** `AB 파일(2개, ITS 실적 통합 데이터)` 업로드 영역과 `CD 파일(2개, CH 변경관리 참고 데이터)` 업로드 영역을 UI 상에서 명확히 구분하여 사용자 실수를 방지.
  3. **결과 출력 영역:** 백엔드에서 응답받은 최종 텍스트를 보여주는 넓은 텍스트 영역(`textarea` 또는 `div`).
  4. **복사 버튼:** 클릭 시 결과 텍스트를 클립보드에 복사하는 버튼(Copy to Clipboard) 필수 구현.
- **통신:** Zustand 스토어 활용, 파일 종류별로 명시적 Key(`file_ab_1`, `file_ab_2`, `file_cd_1`, `file_cd_2`)를 담아 FastAPI 백엔드로 전송 및 응답 수신.

## 5. 에러 핸들링 및 유의사항
- **(추가) 엑셀 파싱 예외:** `header=2` 위치에 기대하는 컬럼이 없거나 확장자가 잘못된 경우 HTTP 400 에러와 함께 "양식에 맞지 않는 엑셀 파일입니다" 등의 명확한 메시지를 반환.
- Pandas에서 T열 결측치 처리 시 `NaN` 체크 유의.
- **(추가) Gemini API 예외:** API 호출 실패 시 간단한 Retry 로직 구현. 타임아웃/오류 지속 시 해당 건은 원본 텍스트를 그대로 유지하고 에러 로그를 남김.
- Gemini API Key는 `.env` 파일에서 `GEMINI_API_KEY`로 읽어옴. (Google Sheets 인증은 불필요하므로 제외)

---

## 6. 개발 로드맵 및 진행 상황

> 각 Task는 독립적인 Git 브랜치에서 작업하기 좋은 단위로 구성되어 있습니다.
> 작업 완료 시 해당 항목의 `[ ]`를 `[x]`로 체크하여 진행 상황을 관리합니다.

---

### [ ] Task 1: 백엔드 의존성 추가 및 도메인 패키지·스키마 구조 생성

**목표:** 실제 구현 전 환경 설정과 데이터 구조를 먼저 확정한다.

**수정/생성 파일:**
- `requirements.txt` / `pyproject.toml`
  - `pandas`, `openpyxl`, `google-generativeai` 패키지 추가
- `server/app/core/config.py`
  - `GEMINI_API_KEY` 환경변수 항목 추가
- `server/app/domain/weekly_report/__init__.py`
  - 도메인 패키지 초기화 파일 생성
- `server/app/domain/weekly_report/schemas.py`
  - `WeeklyReportRequest`: 날짜(`report_date`) + 4개 파일 key (`file_ab_1`, `file_ab_2`, `file_cd_1`, `file_cd_2`) 정의
  - `WeeklyReportResponse`: 최종 포맷팅 텍스트(`result_text: str`) 정의

---

### [ ] Task 2: Calculator 레이어 — Excel 파싱 및 데이터 필터링·매핑 구현

**목표:** Gemini 없이 순수 Pandas 로직만으로 필터링·매핑까지 완성한다.

**수정/생성 파일:**
- `server/app/domain/weekly_report/calculator.py`
  - **로직 1 (통합):** `pd.read_excel(header=2)`로 AB 2개 파일 concat, CD 2개 파일 concat
  - **로직 2 (필터링):**
    - F열 또는 W열이 지정 시스템값인 행만 추출
    - T열 유무에 따라 P열 또는 Z열 날짜를 기준으로 해당 주(월~금) 포함 여부 판별; 빈 값이면 무조건 포함
    - T열 결측치 `NaN` 처리 주의
  - **로직 3 (기본 데이터 매핑):**
    - 요청 ID (A열), 진행상태 (B열 → 완료/대기/진행중 변환)
    - 일정 (P열 → 없으면 O열, `MM/DD` 포맷)
    - 구분 (T열 없으면 C열; T열 있으면 CD 파일과 join 후 D열 확인 → 개발/개선 or 프로젝트/운영)
  - **로직 4-전처리 (원본 텍스트 추출):**
    - T열 없는 건: G열(제목), H열(요구사항); P열에 값 있으면 R열(처리내용) 추가
    - T열 있는 건: G열(제목), H열(요구사항); Z열에 값 있으면 AB열(처리내용) 추가

---

### [ ] Task 3: Calculator 레이어 — Gemini API 연동 구현

**목표:** Task 2에서 추출한 원본 텍스트를 Gemini API로 윤문 처리하는 비동기 로직을 추가한다.

**수정/생성 파일:**
- `server/app/domain/weekly_report/calculator.py` (Gemini 파트 추가)
  - `google-generativeai` SDK 초기화 (config에서 `GEMINI_API_KEY` 주입)
  - 프롬프트 구성: 원본 텍스트 → `[제목]`, `[개요]`, `[내용]` 각 1~2줄 비즈니스 요약 지시
  - `asyncio.Semaphore`로 동시 호출 수 제한 또는 다건 데이터를 JSON 배열로 묶어 Batch 처리
  - 실패 시 원본 텍스트 유지 + 에러 로그 기록 (간단한 Retry 로직 포함)

---

### [ ] Task 4: Formatter 레이어 구현

**목표:** Calculator의 정제 데이터를 최종 복사용 텍스트 문자열로 변환한다.

**수정/생성 파일:**
- `server/app/domain/weekly_report/formatter.py`
  - J열(요청회사) 기준으로 창원 / 베스틸 항목 분류
  - 아래 포맷으로 텍스트 생성 (처리내용 없는 항목은 `-. 내용` 라인 생략):
    ```
    ◈EPRO 운영
    [창원]
    ▣ ({구분}) ({요청 ID}) {제목} (~{mm/dd}, {진행상태})
      -. 개요 : {개요}
      -. 내용 : {내용}

    [베스틸]
    ▣ ({구분}) ({요청 ID}) {제목} (~{mm/dd}, {진행상태})
      -. 개요 : {개요}
      -. 내용 : {내용}
    ```
  - 해당 분류에 항목이 없을 경우 해당 섹션 생략 처리

---

### [ ] Task 5: Service + Router 레이어 구현 및 API 등록

**목표:** 백엔드 전체 레이어를 연결하고 엔드포인트를 외부에 노출한다.

**수정/생성 파일:**
- `server/app/domain/weekly_report/service.py`
  - `Calculator`, `Formatter` 인스턴스를 주입받아 워크플로우 조율
  - 사전 검증: 파일이 정상 Excel인지, `header=2` 위치에 필수 컬럼 존재 여부 확인
  - 검증 실패 시 HTTP 400 + 명확한 에러 메시지 반환
- `server/app/domain/weekly_report/router.py`
  - `POST /api/v1/weekly-report/generate` 엔드포인트 구현
  - `report_date` + `UploadFile` 4개(`file_ab_1`, `file_ab_2`, `file_cd_1`, `file_cd_2`) 수신
  - Service 호출 후 최종 텍스트 반환
- `server/app/api/v1/router.py`
  - `weekly_report` 라우터를 메인 API 라우터에 등록

---

### [ ] Task 6: 프론트엔드 타입 / API 클라이언트 / Zustand 스토어 구현

**목표:** UI 없이 데이터 레이어만 먼저 완성하여 백엔드 연동을 검증한다.

**수정/생성 파일:**
- `client/src/domains/weeklyits/types.ts`
  - `WeeklyReportFiles`: `file_ab_1`, `file_ab_2`, `file_cd_1`, `file_cd_2` (`File | null`) 타입
  - `WeeklyReportState`: 날짜, 파일 상태, 결과 텍스트, 로딩/에러 상태 타입
- `client/src/domains/weeklyits/api.ts`
  - `generateWeeklyReport(reportDate: string, files: WeeklyReportFiles): Promise<string>`
  - `FormData`에 날짜와 4개 파일을 명시적 key로 담아 `POST /api/v1/weekly-report/generate` 호출
- `client/src/domains/weeklyits/store.ts`
  - Zustand 스토어: 파일 set/clear 액션, 날짜 set 액션, 결과·로딩·에러 상태 관리
  - `generateReport()` 액션: API 호출 → 결과 상태 업데이트

---

### [ ] Task 7: 프론트엔드 UI 컴포넌트 및 페이지 조립

**목표:** 사용자가 실제로 사용 가능한 완성된 화면을 구현한다.

**수정/생성 파일:**
- `client/src/domains/weeklyits/components/WeeklyReportDatePicker.tsx`
  - 주간 날짜 선택 입력 UI (date input 또는 라이브러리 활용)
  - 선택 값을 스토어의 날짜 상태에 반영
- `client/src/domains/weeklyits/components/FileUploadSection.tsx`
  - **AB 파일 영역**: `file_ab_1`, `file_ab_2` 각각의 업로드 입력 (라벨로 명확히 구분)
  - **CD 파일 영역**: `file_cd_1`, `file_cd_2` 각각의 업로드 입력 (라벨로 명확히 구분)
  - 선택된 파일명 표시, 파일 초기화 버튼
- `client/src/domains/weeklyits/components/WeeklyReportResult.tsx`
  - 결과 텍스트 표시용 `<textarea>` 또는 `<pre>` 영역 (읽기 전용)
  - **Copy to Clipboard 버튼**: 클릭 시 `navigator.clipboard.writeText()` 호출 + 완료 피드백
- `client/src/domains/weeklyits/pages/WeeklyItsPage.tsx`
  - 위 컴포넌트들을 레이아웃에 배치
  - 스토어 연결: 제출 버튼 클릭 → `generateReport()` 액션 호출
  - 로딩 스피너 및 에러 메시지 표시
- `client/src/domains/weeklyits/index.ts`
  - 도메인 공개 API export 정리
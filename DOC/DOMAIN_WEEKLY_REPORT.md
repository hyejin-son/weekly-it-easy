# 프로젝트: 주간보고 자동화 도메인 추가 (FastAPI + React)

## 1. 개요
사용자가 업로드한 4개의 ITS/어플리케이션 변경관리 엑셀 파일을 분석하여 주간보고 양식을 생성하고, **그 결과를 프론트엔드 화면에 텍스트로 출력하여 사용자가 복사(Copy)할 수 있도록 제공**하는 기능을 추가한다.
**이 기능은 프로젝트의 `ARCHITECTURE.md` 및 `DEVELOPMENT_GUIDE.md`를 엄격히 준수하는 새로운 도메인(`weekly_report`)으로 구현되어야 한다.**

---

## 2. 아키텍처 개요 — 2-Step 방식 (Phase 4 리팩토링)

> **배경:** 단일 API 호출(엑셀 파싱 + AI 윤문 동시 처리) 방식은 데이터량이 많을 경우 120초 타임아웃을 초과하는 문제가 발생했다. 이를 해결하기 위해 전체 흐름을 **2-Step**으로 분리한다.

### 전체 흐름

```
[Step 1 — Extract]
  사용자: 날짜 + 파일 4개 업로드 → "데이터 추출" 클릭
  백엔드: 엑셀 파싱 + 필터링 + 기본 매핑 (AI 호출 없음, 매우 빠름)
  프론트: 파싱된 레코드를 미리보기 테이블로 노출

                  ↓ 사용자가 테이블 내용 확인

[Step 2 — Generate]
  사용자: "주간보고 생성" 클릭
  백엔드: 미리보기 레코드를 받아 Gemini AI 윤문 + 포맷팅
  프론트: 최종 주간보고 텍스트 출력 + 복사 버튼 활성화
```

### Step 분리 근거

| 구분 | Step 1 (Extract) | Step 2 (Generate) |
|------|-----------------|-------------------|
| 엔드포인트 | `POST /api/v1/weekly-report/extract` | `POST /api/v1/weekly-report/generate` |
| 입력 | `report_date` + 파일 4개 (multipart) | `report_date` + `records` (JSON body) |
| AI 호출 | 없음 | Gemini API 윤문 처리 |
| 응답 속도 | 빠름 (수 초) | 느림 (AI 처리 시간 의존) |
| 출력 | `WeeklyReportRecord[]` (구조화 데이터) | `result_text` (최종 포맷팅 텍스트) |

---

## 3. 기술 스택 및 아키텍처 원칙
- **Backend**: Python 3.12, FastAPI, Pydantic
- **Frontend**: React 19, TypeScript, Zustand
- **AI Integration**: `google-generativeai` (Gemini API)
- **디자인 패턴**: 계층화된 아키텍처 (`Router` → `Service` → `Calculator` / `Formatter`)
- **제외 사항**: 본 도메인은 DB나 외부 Google Sheets API와 통신하지 않으므로 `Repository` 계층은 생략하거나 Mocking 처리한다.

---

## 4. 데이터 스키마 (Pydantic)

### 공통 레코드 단위 — `WeeklyReportRecord`
Step 1 응답 및 Step 2 요청에서 공유하는 단위 데이터 구조.

| 필드 | 타입 | 설명 |
|------|------|------|
| `request_id` | `str` | A열 — 요청 ID |
| `company` | `str` | J열 — 요청회사 (창원 / 베스틸) |
| `biz_system` | `str` | E열 또는 F열 — 업무시스템 |
| `biz_system2` | `str` | W열 — 업무시스템2 (필터링 기준) |
| `category` | `str` | 구분 (개발/개선 또는 프로젝트/운영) |
| `status` | `str` | 진행상태 (완료 / 대기 / 진행중) |
| `schedule` | `str` | 일정 (~mm/dd 포맷, 없으면 빈 문자열) |
| `title_raw` | `str` | G열 — 제목 원본 |
| `summary_raw` | `str` | H열 — 요구사항 원본 |
| `content_raw` | `str \| None` | R열 또는 AB열 — 처리내용 원본 (없으면 null) |

### Step 1 — Extract API 스키마

**Request:** `multipart/form-data`
- `report_date: str` — 보고 기준 날짜
- `file_ab_1`, `file_ab_2`, `file_cd_1`, `file_cd_2`: `UploadFile`

**Response:** `ExtractResponse`
```python
class ExtractResponse(BaseModel):
    records: list[WeeklyReportRecord]
```

### Step 2 — Generate API 스키마

**Request:** `application/json` (`GenerateRequest`)
```python
class GenerateRequest(BaseModel):
    report_date: str
    records: list[WeeklyReportRecord]
```

**Response:** `WeeklyReportResponse` (기존 유지)
```python
class WeeklyReportResponse(BaseModel):
    result_text: str
```

---

## 5. 백엔드 도메인 설계 (Layer별 역할)

### 5.1. Router Layer (`router.py`)

**역할:** 두 개의 엔드포인트를 외부에 노출하고 요청/응답 직렬화를 담당.

#### `POST /api/v1/weekly-report/extract`
- **입력:** `report_date` + 파일 4개 (`multipart/form-data`)
- **처리:** Service의 `extract_records()` 호출
- **출력:** `ExtractResponse { records: WeeklyReportRecord[] }`
- **파일 비즈니스 의미:**
  - **AB 파일** (2개): 베스틸 + 창원의 **ITS 서비스 및 변경 실적 데이터 (SR+CH 통합)** — 메인 분석 대상
  - **CD 파일** (2개): 베스틸 + 창원의 **어플리케이션 변경관리 이력 데이터 (CH 참고용)** — AB 파일의 T열(변경 ID) 조인용
  - **⚠ 주의:** AB/CD 구분은 데이터 성격(ITS vs CH) 기준이며, 창원/베스틸 분류는 각 파일 내 **J열(요청회사)** 값으로만 결정됨

#### `POST /api/v1/weekly-report/generate`
- **입력:** `GenerateRequest { report_date, records }` (JSON body)
- **처리:** Service의 `generate_report()` 호출 (AI 윤문 + 포맷팅)
- **출력:** `WeeklyReportResponse { result_text: str }`

---

### 5.2. Calculator Layer (`calculator.py`)

**역할:** Step별로 명확히 분리된 두 메서드를 제공.

#### `extract(files, report_date) → list[WeeklyReportRecord]`
Step 1 전용. AI 호출 없이 순수 Pandas 로직만으로 빠르게 처리.

- **로직 1 (통합):** `pd.read_excel(header=2)`로 AB 2개 파일 concat, CD 2개 파일 concat. 인덱스 초기화(`ignore_index=True`).
- **로직 2 (필터링):**
  - AB 파일의 F열 또는 W열(업무시스템2)이 아래 값 중 하나인 행만 추출:
    - `'세아베스틸>기타>e-Procurement'`
    - `'세아창원특수강>기타>e-Procurement'`
  - **B열(진행상태) 제외 필터 — T열 없는 행에만 적용:**
    - T열(변경 ID)이 NaN인 행: B열 값이 `'취소종료'` 또는 `'중단종료'`이면 제외
    - T열이 있는 행: 이 단계에서 상태 필터 미적용. CH 제외 기준(아래 로직 3 참조)은 매핑 단계에서 결정.
  - T열(변경 ID) 결측 여부(`pd.isna()`)에 따라 날짜 기준 열 분기:
    - T열 없음(NaN) → P열(처리완료일) 기준
    - T열 있음 → Z열 기준
  - 날짜 필터: 사용자 입력 날짜의 해당 주(월~금)에 포함되면 추출. **날짜 값이 비어있으면(진행 중/대기) 무조건 포함.**
- **로직 3 (기본 데이터 매핑):**
  - 요청 ID: A열 / 회사: J열 / 업무시스템: F열 / 업무시스템2: W열
  - 일정(`~mm/dd`): P열 (없으면 O열), `MM/DD` 포맷으로 변환

  **[진행상태 — 조건부 매핑]**

  > 모든 상태값 비교 시 문자열 내부 공백을 포함한 모든 공백을 제거 후 판단한다.
  > (Pandas 시리즈: `.str.replace(r'\s+', '', regex=True)`, 단일 값: `re.sub(r'\s+', '', val)`)

  | 조건 | 기준 | 완료 | 대기 | 진행중 | 제외(행 삭제) |
  |------|------|------|------|--------|--------------|
  | T열 없음 | AB 파일 B열 | 종료, 요청처리확인, 요청처리승인 | SR사전검토, SR사전검토승인, 요청접수및분류 | 그 외 | 취소종료, 중단종료 (필터링 단계) |
  | T열 있음 | CD 파일 B열 (조인 키: AB.T == CD.A) | 변경승인, 운영자확인, 요청자확인, 배포요청, 배포승인, 배포담당자확인, 배포결과확인, 종료, 사후처리종료 | 변경등록, 재등록, 변경사후등록, 변경사후재등록, 접수 및 검토 | 그 외 | 기각종료, 중단종료 (매핑 단계) |
  | T열 있음 + CD 미발견 | AB 파일 B열 (Fallback) | 위 AB 기준 동일 | 위 AB 기준 동일 | 위 AB 기준 동일 | — |

  > **Fallback 정책:** T열이 있어 CD 파일을 조회했으나 해당 변경 ID가 존재하지 않는 경우,
  > `logger.warning("변경 ID {id}를 CD 파일에서 찾을 수 없어 AB 파일 기준으로 폴백합니다")` 를 기록하고
  > AB 파일 B열(상태) / C열(구분)을 기준으로 처리한다.

  **[구분(Category) — 조건부 매핑]**

  | 조건 | 기준 | 개발/개선 | 프로젝트/운영 |
  |------|------|----------|-------------|
  | T열 없음 | AB 파일 C열 | `전산개발신규요청`, `전산개발수정요청` 포함 시 (공백 제거 후 부분 일치) | 그 외 |
  | T열 있음 | CD 파일 D열 (조인 키: AB.T == CD.A) | `전산개발신규요청`, `전산개발수정요청` 포함 시 (공백 제거 후 부분 일치) | 그 외 |
  | T열 있음 + CD 미발견 | AB 파일 C열 (Fallback) | `전산개발신규요청`, `전산개발수정요청` 포함 시 (공백 제거 후 부분 일치) | 그 외 |

  > ※ 단, 값 비교 시 띄어쓰기를 모두 제거하고, '전산개발신규요청' 또는 '전산개발수정요청' 문자열이
  > 포함되어 있는지(부분 일치)를 기준으로 판단한다.
  > (예: "서비스요청 > 전산개발신규 요청" → 공백 제거 후 "서비스요청>전산개발신규요청" → 부분 일치 → "개발/개선")

  > **조인 키:** CD 파일 조인 시 **AB 파일 T열(변경 ID) == CD 파일 A열(CH ID)** 를 키로 사용한다.
  > (구 코드의 AB.A == CD.A 조인은 SR ID 기반으로 잘못된 조인이었으며, 이번 변경에서 수정됨.)
- **로직 4 (원본 텍스트 추출):**
  - T열 없는 건: G열(제목), H열(요구사항); P열에 값 있으면 R열(처리내용) 추가
  - T열 있는 건: G열(제목), H열(요구사항); Z열에 값 있을 때,
    - B열(진행상태)에 '종료' 포함 시 → R열(처리내용) 추가 (종료 건은 AB열보다 상세한 R열 우선 참조)
    - B열(진행상태)에 '종료' 미포함 시 → AB열(처리내용) 추가

#### `refine(records) → list[WeeklyReportRecord]`
Step 2 전용. 레코드 리스트를 받아 AI 윤문 후 반환. 파일 파싱 없음.

- **AI 윤문 (`google-generativeai` 비동기 호출):**
  - `title_raw`, `summary_raw`, `content_raw`를 프롬프트로 전달
  - 프롬프트 지시: `[제목]`, `[개요]`, `[내용]` 각 1~2줄, 비즈니스 용어, 인사말·이름 제거
  - 윤문 결과를 `WeeklyReportRecord`의 별도 필드(`title`, `summary`, `content`)에 저장
- **Rate Limit 방어:**
  - 다수 레코드를 JSON 배열 프롬프트로 묶어 단일 Batch API 호출로 처리
- **예외 처리:**
  - API 호출 실패 시 최대 2회 Retry (지수 백오프)
  - Retry 후에도 실패 시 원본 텍스트(`*_raw` 필드) 그대로 사용 + 에러 로그

---

### 5.3. Formatter Layer (`formatter.py`)

**역할:** `refine()` 완료 레코드 리스트를 최종 복사용 텍스트 문자열로 변환.

**분류 기준:** J열(요청회사) → 창원 / 베스틸 섹션 분리

**출력 포맷 (정확히 준수):**
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

**조건부 처리:**
- `-. 내용` 라인: 처리내용이 있는 경우에만 포함, 없으면 해당 라인 생략
- 해당 분류에 항목이 없으면 `[창원]` / `[베스틸]` 섹션 전체 생략

---

### 5.4. Service Layer (`service.py`)

**역할:** Router의 요청을 받아 `Calculator`, `Formatter`를 주입받아 워크플로우를 조율.

**메서드 구성:**
- `extract_records(files, report_date) → ExtractResponse`
  - 파일 사전 검증(확장자, 필수 컬럼) → `calculator.extract()` 호출 → `ExtractResponse` 반환
- `generate_report(request: GenerateRequest) → WeeklyReportResponse`
  - `calculator.refine(records)` → `formatter.format(refined_records)` → `WeeklyReportResponse` 반환

**사전 검증 항목 (extract 단계에서 수행):**
- 4개 파일 모두 `.xlsx` 또는 `.xls` 확장자 확인
- `pd.read_excel(header=2)` 기준 파일 유형별 최소 컬럼 수 확인:
  - AB 파일 (ITS 서비스/변경 이력): 최소 **28개** — AB열(index 27)까지 사용 (`MIN_REQUIRED_COLS = 28`)
  - CD 파일 (CH 변경관리 이력): 최소 **14개** — D열(index 3) lookup만 사용 (`MIN_REQUIRED_COLS_CD = 14`)
- 검증 실패 시 `HTTPException(status_code=400)` + `"양식에 맞지 않는 엑셀 파일입니다"` 메시지

---

## 6. 프론트엔드 설계

### UI 흐름 (2-Step)

```
[Step 1 — 데이터 추출]
1. 날짜 선택 (DatePicker)
2. 파일 업로드 (AB 영역 2개 + CD 영역 2개, 시각적으로 구분)
3. "데이터 추출" 버튼 클릭
4. → 미리보기 테이블 노출 (Step 1 결과)

[Step 2 — 보고서 생성]
5. 사용자가 테이블 데이터 확인
6. "주간보고 생성" 버튼 클릭 (Step 1 완료 후 활성화)
7. → AI 처리 로딩 스피너 표시
8. → 최종 텍스트 출력 + 복사 버튼
```

### 미리보기 테이블 (`WeeklyReportPreviewTable.tsx`)

Step 1 응답(`records`)을 테이블로 시각화. 컬럼 구성 (8개):

| # | 컬럼명 | 데이터 소스 |
|---|--------|------------|
| 1 | 요청 ID | `request_id` |
| 2 | 회사 | `company` (창원 / 베스틸) |
| 3 | 업무시스템 | `biz_system` |
| 4 | 업무시스템2 | `biz_system2` |
| 5 | 구분 | `category` |
| 6 | 진행상태 | `status` |
| 7 | 일정 | `schedule` |
| 8 | 제목(원본) | `title_raw` |

### 컴포넌트 구성

| 컴포넌트 | 역할 |
|---------|------|
| `WeeklyReportDatePicker.tsx` | 날짜 선택 — 스토어 `setReportDate()` 연결 |
| `FileUploadSection.tsx` | AB/CD 파일 업로드 영역 시각 구분 (기존 유지) |
| `WeeklyReportPreviewTable.tsx` | **[신규]** Step 1 결과 미리보기 테이블 |
| `WeeklyReportResult.tsx` | Step 2 결과 텍스트 + 복사 버튼 |
| `WeeklyItsPage.tsx` | 전체 2-Step 흐름 조율 |

### Zustand 스토어 상태

```typescript
interface WeeklyReportState {
  // Step 1 입력
  reportDate: string;
  files: WeeklyReportFiles;       // file_ab_1, file_ab_2, file_cd_1, file_cd_2
  // Step 1 결과
  extractedRecords: WeeklyReportRecord[];
  isExtracted: boolean;
  isExtracting: boolean;
  // Step 2 결과
  resultText: string;
  isGenerating: boolean;
  // 공통
  error: string | null;
}
```

### API 클라이언트 함수

```typescript
// Step 1
extractWeeklyReport(reportDate: string, files: WeeklyReportFiles): Promise<WeeklyReportRecord[]>
// → POST /api/v1/weekly-report/extract (multipart/form-data)

// Step 2
generateWeeklyReport(reportDate: string, records: WeeklyReportRecord[]): Promise<string>
// → POST /api/v1/weekly-report/generate (application/json)
```

### 통신 방식

- Step 1: `FormData`에 `report_date`와 4개 파일을 담아 `multipart/form-data` 전송
- Step 2: `{ report_date, records }` JSON body 전송 (파일 재전송 불필요)

---

## 7. 에러 핸들링 및 유의사항

- **엑셀 파싱 예외 (Step 1에서 처리):** `header=2` 기준 컬럼이 없거나 확장자가 잘못된 경우 HTTP 400 + 명확한 메시지 반환
- **T열 결측치:** 반드시 `pd.isna()` 또는 `.isnull()`로 체크 (`== NaN` 비교 금지)
- **Gemini API 예외 (Step 2에서 처리):** 실패 시 최대 2회 Retry. 지속 실패 시 원본 텍스트 유지 + 에러 로그
- **Gemini API Key:** `.env` 파일에서 `GEMINI_API_KEY`로 읽어옴
- **특수문자 보존:** `◈`, `▣` 등은 하드코딩. 프론트 결과 텍스트 영역은 `white-space: pre` 또는 `<pre>` 태그 사용
- **Clipboard API:** `navigator.clipboard.writeText()`는 HTTPS 또는 localhost에서만 동작

---

## 8. 개발 로드맵 및 진행 상황

> 상세 Task 명세는 `DOC/ROADMAP-WEEKLY-REPORT.md`를 참조.
> **Phase 0 ~ Phase 3 (완료):** 단일 API 방식의 초기 구현 완료.
> **Phase 4 (진행 예정):** 2-Step 아키텍처 리팩토링.

| Phase | 상태 | 내용 |
|-------|------|------|
| Phase 0 | ✅ 완료 | 환경 준비 (의존성, 스키마 구조) |
| Phase 1 | ✅ 완료 | 백엔드 계산 로직 (Pandas + Gemini) |
| Phase 2 | ✅ 완료 | 백엔드 포매팅 + 서비스/라우터 |
| Phase 3 | ✅ 완료 | 프론트엔드 초기 구현 |
| **Phase 4** | 🔲 예정 | **2-Step 아키텍처 리팩토링** |

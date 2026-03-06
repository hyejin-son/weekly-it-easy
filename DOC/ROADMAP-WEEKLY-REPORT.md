# 주간보고 자동화 — 구현 로드맵 및 작업 태스크

> **기준 문서:** `DOC/DOMAIN_WEEKLY_REPORT.md`
> **작성 기준 시점:** 프로젝트 초기 세팅 완료 상태 (아래 "현재 완료 목록" 참고)
> **작업 단위:** Task 1개 = Claude Code 세션 1회 = Git 브랜치 1개

---

## 현재 완료 상태 (구현 불필요)

- `BaseService`, `BaseCalculator`, `BaseFormatter` 추상 클래스 (`server/app/shared/base/`)
- 도메인 폴더 스캐폴딩 (`server/app/domain/`, `client/src/domains/weeklyits/`)
- 프론트엔드 stub 파일 생성 (`types.ts`, `api.ts`, `store.ts`, `WeeklyItsPage.tsx` — 내용 비어있음)
- 샘플 도메인 레퍼런스 구현 (`server/app/examples/sample_domain/`, `client/src/domains/sample/`)
- API v1 라우터 등록 구조 (`server/app/api/v1/router.py`)

---

## Phase 의존 관계

```
Phase 0 (환경 준비)
    └── Phase 1 (백엔드 계산 로직)
            ├── Task 1-1: Calculator — Pandas 로직
            └── Task 1-2: Calculator — Gemini 연동 (Task 1-1 선행)
                └── Phase 2 (백엔드 포매팅·서비스·라우터)
                        ├── Task 2-1: Formatter
                        └── Task 2-2: Service + Router (Task 2-1 선행)
                            └── Phase 3 (프론트엔드)
                                    ├── Task 3-1: 타입·API 클라이언트·스토어
                                    └── Task 3-2: UI 컴포넌트·페이지 (Task 3-1 선행)
```

---

## Phase 0 — 환경 준비

> **선행 조건:** 없음 (가장 먼저 수행)
> **목적:** 이후 모든 Phase의 기반이 되는 의존성, 환경 변수, 도메인 패키지 구조, 데이터 스키마를 확정한다.

---

### - [x] Task 0-1: 백엔드 의존성 추가 + 도메인 패키지 구조 생성 + 스키마 정의

**작업 목표**
실제 구현 전에 패키지 환경과 데이터 계약(스키마)을 먼저 확정하여 이후 Task들이 명확한 인터페이스를 참고할 수 있게 한다.

**작업 범위 (수정/생성 파일)**

| 구분 | 파일 경로 | 작업 내용 |
|------|-----------|-----------|
| 수정 | `requirements.txt` | `pandas`, `openpyxl`, `google-generativeai` 추가 |
| 수정 | `pyproject.toml` | 동일 패키지 dependencies 섹션에 추가 |
| 수정 | `server/app/core/config.py` | `GEMINI_API_KEY: str` 환경변수 항목 추가 |
| 생성 | `server/app/domain/weekly_report/__init__.py` | 도메인 패키지 초기화 |
| 생성 | `server/app/domain/weekly_report/schemas.py` | 요청/응답 스키마 정의 |

**스키마 상세 (`schemas.py`)**
- `WeeklyReportRequest`: `report_date: str` + `file_ab_1`, `file_ab_2`, `file_cd_1`, `file_cd_2` (`UploadFile`)
- `WeeklyReportResponse`: `result_text: str`

**완료 기준**
- `pip install -r requirements.txt` 실행 시 세 패키지 모두 정상 설치
- `from server.app.domain.weekly_report.schemas import WeeklyReportRequest` import 오류 없음
- `config.py`에서 `settings.GEMINI_API_KEY` 접근 가능 (`.env`에 값 없어도 구조는 존재)

**주의사항**
- `.env.example`에도 `GEMINI_API_KEY=` 항목 추가하여 팀원에게 안내
- `google-generativeai` 버전은 최신 stable 버전 명시 (예: `>=0.8.0`)
- `pyproject.toml`과 `requirements.txt` 양쪽 모두 업데이트 (두 파일이 병행 관리됨)

---

## Phase 1 — 백엔드 계산 로직

> **선행 조건:** Phase 0 완료
> **목적:** Excel 파일에서 데이터를 읽고 필터링·매핑·AI 윤문까지 완성한다.

---

### - [x] Task 1-1: Calculator — Excel 파싱 + 데이터 필터링·매핑 구현

**작업 목표**
Gemini 없이 순수 Pandas 로직만으로 Excel 통합 → 필터링 → 데이터 매핑 → 원본 텍스트 추출까지 완성한다.

**작업 범위 (수정/생성 파일)**

| 구분 | 파일 경로 | 작업 내용 |
|------|-----------|-----------|
| 생성 | `server/app/domain/weekly_report/calculator.py` | 로직 1~4 전처리 구현 |

**구현 로직 상세**

**로직 1 — 파일 통합**
- `pd.read_excel(file, header=2)` 로 AB 파일 2개 `pd.concat`, CD 파일 2개 `pd.concat`
- 인덱스 초기화(`ignore_index=True`)

**로직 2 — 필터링**
- F열 또는 W열(업무시스템2)이 아래 값 중 하나인 행만 추출:
  - `'세아베스틸>기타>e-Procurement'`
  - `'세아창원특수강>기타>e-Procurement'`
- T열(변경 ID) 결측 여부에 따라 날짜 기준 열 분기:
  - T열 없음(NaN) → P열(처리완료일) 기준
  - T열 있음 → Z열 기준
- 날짜 필터: 사용자 입력 날짜의 해당 주 월요일~금요일에 포함되면 추출; **날짜 값이 비어있으면(진행 중/대기) 무조건 포함**

**로직 3 — 기본 데이터 매핑**

| 항목 | 매핑 규칙 |
|------|-----------|
| 요청 ID | A열 |
| 진행상태 | B열 값 → `'종료/중단종료/취소종료'` → `완료` / `'요청 접수 및 분류'` → `대기` / 그 외 → `진행중` |
| 일정 (`~mm/dd`) | P열 (없으면 O열), `MM/DD` 포맷으로 변환 |
| 구분 | T열 없음 → C열 값 / T열 있음 → CD 파일과 join 후 D열 확인 → `'서비스요청 > 전산개발수정/신규 요청'`이면 `개발/개선`, 그 외 `프로젝트/운영` |

**로직 4 (전처리) — 원본 텍스트 추출**

| 조건 | 추출 컬럼 |
|------|-----------|
| T열 없음 | G열(제목), H열(요구사항); P열에 값 있으면 R열(처리내용) 추가 |
| T열 있음 | G열(제목), H열(요구사항); Z열에 값 있으면 AB열(처리내용) 추가 |

**완료 기준**
- 실제 샘플 Excel 파일(또는 Mock 데이터)로 함수 호출 시 필터링·매핑된 레코드 리스트가 반환됨
- 날짜가 빈 행(대기/진행 중)이 항상 포함되는 것 확인
- T열 유무에 따라 날짜 기준 열이 올바르게 분기되는 것 확인

**주의사항**
- T열 결측치는 반드시 `pd.isna()` 또는 `.isnull()` 로 체크 (`== NaN` 비교 금지)
- AB 열 인덱스는 숫자로 접근 시 27번째 열(0-indexed)임에 주의; 컬럼명 기반 접근 권장
- `header=2` 기준 컬럼명이 예상과 다를 경우를 대비해 컬럼 존재 여부 검증 로직 포함

---

### - [x] Task 1-2: Calculator — Gemini API 연동 구현

> **선행 조건:** Task 1-1 완료

**작업 목표**
Task 1-1에서 추출한 원본 텍스트를 Gemini API로 윤문 처리하는 비동기 로직을 추가하고 Rate Limit 방어 전략을 적용한다.

**작업 범위 (수정/생성 파일)**

| 구분 | 파일 경로 | 작업 내용 |
|------|-----------|-----------|
| 수정 | `server/app/domain/weekly_report/calculator.py` | Gemini 비동기 윤문 로직 추가 |

**구현 상세**

- `google.generativeai` SDK 초기화: `config.py`에서 `GEMINI_API_KEY` 주입
- **프롬프트 구성:**
  원본 텍스트(제목, 요구사항, 처리내용) → `[제목]`, `[개요]`, `[내용]` 각 1~2줄, 비즈니스 용어, 인사말·이름 제거
- **Rate Limit 방어 (둘 중 하나 선택하여 구현):**
  - **방식 A (Semaphore):** `asyncio.Semaphore(5)` 등으로 동시 호출 수 제한 후 건별 비동기 호출
  - **방식 B (Batch):** 다수 레코드를 JSON 배열 프롬프트로 묶어 단일 API 호출로 처리
- **예외 처리:**
  - API 호출 실패 시 최대 2회 Retry (단순 지수 백오프)
  - Retry 후에도 실패 시 원본 텍스트 그대로 유지 + 에러 로그 기록

**완료 기준**
- 유효한 `GEMINI_API_KEY` 환경변수로 실제 API 호출 성공
- 응답에 `[제목]`, `[개요]`, `[내용]` 구조가 파싱되어 각 필드로 분리됨
- API 실패 시나리오에서 원본 텍스트가 유지되고 로그가 남는 것 확인

**주의사항**
- Gemini 응답 파싱은 정규식보다 `[제목]`, `[개요]`, `[내용]` 마커 기반 split이 안전
- 환경변수 없이도 Task 1-1 로직은 동작해야 하므로 Gemini 초기화 실패는 graceful하게 처리
- 비용 절감을 위해 개발/테스트 시 Batch 방식 선호

---

## Phase 2 — 백엔드 포매팅 + 서비스/라우터

> **선행 조건:** Phase 1 완료
> **목적:** 계산된 데이터를 최종 텍스트로 포맷하고 API 엔드포인트로 외부에 노출한다.

---

### - [ ] Task 2-1: Formatter — 최종 텍스트 포맷 생성 구현

**작업 목표**
Calculator에서 정제된 레코드 리스트를 복사 가능한 최종 텍스트 문자열로 변환한다.

**작업 범위 (수정/생성 파일)**

| 구분 | 파일 경로 | 작업 내용 |
|------|-----------|-----------|
| 생성 | `server/app/domain/weekly_report/formatter.py` | 텍스트 포맷 생성 로직 구현 |

**출력 포맷 (정확히 준수)**

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

**분류 기준 및 조건부 처리**
- **창원/베스틸 분류:** J열(요청회사) 값 기준으로 섹션 분리
- **`-. 내용` 라인:** 처리내용(R열 또는 AB열)이 존재하는 경우에만 포함, 없으면 해당 라인 생략
- **섹션 생략:** 창원 또는 베스틸 중 해당 건이 없으면 해당 `[창원]` / `[베스틸]` 섹션 전체 생략

**완료 기준**
- 샘플 레코드 리스트 입력 시 위 포맷과 정확히 일치하는 문자열 반환
- 처리내용 없는 항목에서 `-. 내용` 라인이 누락되는 것 확인
- 창원 항목만 있을 때 `[베스틸]` 섹션이 출력되지 않는 것 확인

**주의사항**
- 특수문자(`◈`, `▣`, `-. `)는 하드코딩으로 정확히 입력 (복사 붙여넣기 권장)
- 줄바꿈 문자는 `\n` 사용, Windows 개행(`\r\n`) 혼입 주의
- 항목이 하나도 없는 경우(빈 결과)에 대한 처리 포함

---

### - [ ] Task 2-2: Service + Router 레이어 구현 및 API 등록

> **선행 조건:** Task 2-1 완료

**작업 목표**
백엔드 전체 레이어(Calculator → Formatter → Service → Router)를 연결하고 `POST /api/v1/weekly-report/generate` 엔드포인트를 외부에 노출한다.

**작업 범위 (수정/생성 파일)**

| 구분 | 파일 경로 | 작업 내용 |
|------|-----------|-----------|
| 생성 | `server/app/domain/weekly_report/service.py` | 워크플로우 조율 + 사전 검증 |
| 생성 | `server/app/domain/weekly_report/router.py` | POST 엔드포인트 구현 |
| 수정 | `server/app/api/v1/router.py` | weekly_report 라우터 등록 |

**Service 상세 (`service.py`)**
- `Calculator`, `Formatter` 인스턴스를 생성자 주입으로 받아 워크플로우 조율
- **사전 검증 항목:**
  - 4개 파일 모두 `.xlsx` 또는 `.xls` 확장자인지 확인
  - `pd.read_excel(header=2)` 로 읽었을 때 필수 컬럼(A, B, F, G, H, J, P, W열) 존재 여부 확인
  - 검증 실패 시 `HTTP 400` + `"양식에 맞지 않는 엑셀 파일입니다"` 메시지 반환

**Router 상세 (`router.py`)**
```
POST /api/v1/weekly-report/generate
  Request: multipart/form-data
    - report_date: str
    - file_ab_1: UploadFile
    - file_ab_2: UploadFile
    - file_cd_1: UploadFile
    - file_cd_2: UploadFile
  Response: WeeklyReportResponse { result_text: str }
```

**완료 기준**
- `uvicorn` 실행 후 `POST /api/v1/weekly-report/generate` 엔드포인트가 Swagger UI에 노출됨
- 정상 파일 4개 + `report_date` 전송 시 포맷팅된 텍스트 응답 수신
- 잘못된 파일 업로드 시 HTTP 400 응답 및 에러 메시지 확인

**주의사항**
- FastAPI `UploadFile`은 비동기 `.read()` 사용: `await file.read()` → `io.BytesIO` 변환 후 pandas 전달
- `server/app/api/v1/router.py`의 기존 라우터 등록 패턴 (`sample` 도메인 참고) 동일하게 적용
- 검증 에러는 FastAPI `HTTPException(status_code=400)` 사용

---

## Phase 3 — 프론트엔드

> **선행 조건:** Phase 2 완료
> **목적:** 사용자가 브라우저에서 파일을 업로드하고 결과를 복사할 수 있는 UI를 완성한다.

---

### - [ ] Task 3-1: 프론트엔드 타입 / API 클라이언트 / Zustand 스토어 구현

**작업 목표**
UI 없이 데이터 레이어(타입, API 통신, 상태 관리)만 먼저 완성하여 백엔드 연동의 기반을 마련한다.

**작업 범위 (수정/생성 파일)**

| 구분 | 파일 경로 | 작업 내용 |
|------|-----------|-----------|
| 수정 | `client/src/domains/weeklyits/types.ts` | stub → 실제 타입 정의 |
| 수정 | `client/src/domains/weeklyits/api.ts` | stub → API 호출 함수 구현 |
| 수정 | `client/src/domains/weeklyits/store.ts` | stub → Zustand 스토어 구현 |

**`types.ts` 상세**
```typescript
interface WeeklyReportFiles {
  file_ab_1: File | null;
  file_ab_2: File | null;
  file_cd_1: File | null;
  file_cd_2: File | null;
}

interface WeeklyReportState {
  reportDate: string;
  files: WeeklyReportFiles;
  resultText: string;
  isLoading: boolean;
  error: string | null;
}
```

**`api.ts` 상세**
- `generateWeeklyReport(reportDate: string, files: WeeklyReportFiles): Promise<string>`
- `FormData`에 `report_date`와 4개 파일을 명시적 key로 담아 `POST /api/v1/weekly-report/generate` 호출
- 응답에서 `result_text` 추출하여 반환

**`store.ts` 상세 (Zustand)**
- 상태: `reportDate`, `files`, `resultText`, `isLoading`, `error`
- 액션:
  - `setReportDate(date: string)`
  - `setFile(key: keyof WeeklyReportFiles, file: File | null)`
  - `clearFiles()`
  - `generateReport()`: API 호출 → 성공 시 `resultText` 업데이트, 실패 시 `error` 설정

**완료 기준**
- TypeScript 컴파일 오류 없음 (`tsc --noEmit`)
- `generateReport()` 액션 호출 시 백엔드 API와 정상 통신 확인 (브라우저 DevTools 기준)
- 파일 set/clear 액션이 스토어 상태에 정확히 반영됨

**주의사항**
- `file_ab_1` 등 key 이름은 백엔드 `FormData` key와 **정확히 일치**해야 함
- `null` 파일이 포함된 경우 `FormData.append` 시 빈 값 전송 방지 (null 체크 후 skip)
- `sample` 도메인의 `api.ts`, `store.ts` 패턴을 레퍼런스로 활용

---

### - [ ] Task 3-2: 프론트엔드 UI 컴포넌트 + 페이지 조립

> **선행 조건:** Task 3-1 완료

**작업 목표**
사용자가 날짜·파일을 입력하고 결과 텍스트를 복사할 수 있는 완성된 UI 페이지를 구현한다.

**작업 범위 (수정/생성 파일)**

| 구분 | 파일 경로 | 작업 내용 |
|------|-----------|-----------|
| 생성 | `client/src/domains/weeklyits/components/WeeklyReportDatePicker.tsx` | 날짜 선택 컴포넌트 |
| 생성 | `client/src/domains/weeklyits/components/FileUploadSection.tsx` | AB/CD 파일 업로드 영역 |
| 생성 | `client/src/domains/weeklyits/components/WeeklyReportResult.tsx` | 결과 표시 + 복사 버튼 |
| 수정 | `client/src/domains/weeklyits/pages/WeeklyItsPage.tsx` | stub → 실제 페이지 조립 |
| 수정 | `client/src/domains/weeklyits/components/index.ts` | 컴포넌트 export 추가 |
| 수정 | `client/src/domains/weeklyits/index.ts` | 도메인 공개 API export 정리 |

**컴포넌트 상세**

**`WeeklyReportDatePicker.tsx`**
- `<input type="date">` 또는 주 단위 선택 UI
- 선택된 날짜를 스토어 `setReportDate()` 액션으로 반영

**`FileUploadSection.tsx`**
- **AB 파일 영역** (`file_ab_1`, `file_ab_2`): 라벨로 명확히 구분 (예: "AB 파일 1", "AB 파일 2")
- **CD 파일 영역** (`file_cd_1`, `file_cd_2`): 동일하게 구분
- 선택된 파일명 표시, 파일별 초기화(X) 버튼
- 스토어 `setFile()` 액션 연결

**`WeeklyReportResult.tsx`**
- 결과 텍스트를 `<textarea readonly>` 또는 `<pre>` 로 표시 (충분한 너비 확보)
- **Copy to Clipboard 버튼:** `navigator.clipboard.writeText(resultText)` 호출
- 복사 완료 시 버튼 텍스트 일시 변경 등 시각적 피드백 제공

**`WeeklyItsPage.tsx`**
- 위 컴포넌트들을 레이아웃에 배치
- **제출 버튼:** 클릭 시 스토어 `generateReport()` 액션 호출
- 로딩 중 스피너 표시 (`isLoading` 상태 기반)
- 에러 발생 시 에러 메시지 표시 (`error` 상태 기반)
- 4개 파일 미선택 시 제출 버튼 비활성화

**완료 기준**
- 브라우저에서 날짜 선택 + 파일 4개 업로드 + 제출 → 결과 텍스트 화면 출력
- "복사" 버튼 클릭 후 다른 곳에 붙여넣기 시 결과 텍스트가 그대로 붙여넣어짐
- 파일 미첨부 상태에서 제출 버튼 비활성화 확인
- 에러 응답 시 화면에 에러 메시지 노출 확인

**주의사항**
- AB 파일 영역과 CD 파일 영역은 UI 상에서 **시각적으로 명확히 구분** (배경색, 테두리, 라벨 등 활용)
- 결과 텍스트 영역은 특수문자(`◈`, `▣`)가 깨지지 않도록 `white-space: pre` 또는 `<pre>` 태그 사용
- `navigator.clipboard` API는 HTTPS 환경 또는 localhost에서만 동작 (개발 환경 확인)
- 기존 `MainLayout` 래퍼 유지하고 내부 컨텐츠만 교체

---

## 전체 체크리스트 요약

### Phase 0
- [x] Task 0-1: 백엔드 의존성 추가 + 도메인 패키지 구조 생성 + 스키마 정의

### Phase 1
- [x] Task 1-1: Calculator — Excel 파싱 + 데이터 필터링·매핑 구현
- [x] Task 1-2: Calculator — Gemini API 연동 구현

### Phase 2
- [ ] Task 2-1: Formatter — 최종 텍스트 포맷 생성 구현
- [ ] Task 2-2: Service + Router 레이어 구현 및 API 등록

### Phase 3
- [ ] Task 3-1: 프론트엔드 타입 / API 클라이언트 / Zustand 스토어 구현
- [ ] Task 3-2: 프론트엔드 UI 컴포넌트 + 페이지 조립

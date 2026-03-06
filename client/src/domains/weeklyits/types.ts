/**
 * WeeklyIts 도메인 타입 정의
 */

export interface WeeklyReportFiles {
  file_ab_1: File | null;
  file_ab_2: File | null;
  file_cd_1: File | null;
  file_cd_2: File | null;
}

/**
 * 백엔드 /extract 엔드포인트가 반환하는 레코드 1건
 * 필드명은 백엔드 Pydantic 모델(WeeklyReportRecord)과 snake_case로 정확히 일치
 */
export interface WeeklyReportRecord {
  request_id: string;
  company: string;
  biz_system: string;
  biz_system2: string;
  category: string;
  status: string;
  schedule: string;
  title_raw: string;
  summary_raw: string;
  content_raw: string | null;
}

export interface WeeklyReportState {
  // Step 1 입력
  reportDate: string;
  files: WeeklyReportFiles;
  // Step 1 결과
  extractedRecords: WeeklyReportRecord[];
  isExtracted: boolean;
  isExtracting: boolean;
  // Step 2 결과
  resultText: string;
  isGenerating: boolean;
  // 공통
  error: string | null;
  // 하위 호환 (Task 4-4 UI 개편 전까지 유지 — isExtracting || isGenerating)
  isLoading: boolean;
}

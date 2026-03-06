/**
 * WeeklyIts 도메인 타입 정의
 */

export interface WeeklyReportFiles {
  file_ab_1: File | null;
  file_ab_2: File | null;
  file_cd_1: File | null;
  file_cd_2: File | null;
}

export interface WeeklyReportState {
  reportDate: string;
  files: WeeklyReportFiles;
  resultText: string;
  isLoading: boolean;
  error: string | null;
}

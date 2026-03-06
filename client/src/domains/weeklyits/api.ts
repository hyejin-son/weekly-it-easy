/**
 * WeeklyIts 도메인 API 함수
 *
 * @important 컴포넌트에서 axios를 직접 사용하지 마세요!
 */

import { apiClient } from '@/core/api';
import type { WeeklyReportFiles, WeeklyReportRecord } from './types';

interface ExtractApiResponse {
  records: WeeklyReportRecord[];
}

interface GenerateApiResponse {
  result_text: string;
}

/**
 * Step 1: 주간보고 데이터 추출 (AI 없음)
 *
 * multipart/form-data로 report_date와 4개의 Excel 파일을 전송하고
 * 파싱·필터링된 레코드 배열을 반환합니다.
 */
export async function extractWeeklyReport(
  reportDate: string,
  files: WeeklyReportFiles
): Promise<WeeklyReportRecord[]> {
  const formData = new FormData();
  formData.append('report_date', reportDate);

  // null이 아닌 파일만 append (백엔드 FormData key 이름과 정확히 일치)
  if (files.file_ab_1 !== null) formData.append('file_ab_1', files.file_ab_1);
  if (files.file_ab_2 !== null) formData.append('file_ab_2', files.file_ab_2);
  if (files.file_cd_1 !== null) formData.append('file_cd_1', files.file_cd_1);
  if (files.file_cd_2 !== null) formData.append('file_cd_2', files.file_cd_2);

  const response = await apiClient.post<ExtractApiResponse>(
    '/v1/weekly-report/extract',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000, // 실무 엑셀 4개 파싱·병합 연산 대기 시간 확보 (120초)
    }
  );

  return response.data.records;
}

/**
 * Step 2: 주간보고 생성 (Gemini AI 윤문 + 포맷팅)
 *
 * Step 1에서 추출한 records 배열을 JSON body로 전송하고
 * 포맷팅된 주간보고 텍스트를 반환합니다.
 */
export async function generateWeeklyReport(
  reportDate: string,
  records: WeeklyReportRecord[]
): Promise<string> {
  const response = await apiClient.post<GenerateApiResponse>(
    '/v1/weekly-report/generate',
    { report_date: reportDate, records },
    {
      headers: { 'Content-Type': 'application/json' },
      timeout: 120000, // Gemini API 배치 처리 대기 시간 확보 (120초)
    }
  );

  return response.data.result_text;
}

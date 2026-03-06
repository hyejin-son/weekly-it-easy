/**
 * WeeklyIts 도메인 API 함수
 *
 * @important 컴포넌트에서 axios를 직접 사용하지 마세요!
 */

import { apiClient } from '@/core/api';
import type { WeeklyReportFiles } from './types';

interface WeeklyReportApiResponse {
  result_text: string;
}

/**
 * 주간보고 생성
 *
 * multipart/form-data로 report_date와 4개의 Excel 파일을 전송하고
 * 포맷팅된 주간보고 텍스트를 반환합니다.
 */
export async function generateWeeklyReport(
  reportDate: string,
  files: WeeklyReportFiles
): Promise<string> {
  const formData = new FormData();
  formData.append('report_date', reportDate);

  // null이 아닌 파일만 append (백엔드 FormData key 이름과 정확히 일치)
  if (files.file_ab_1 !== null) formData.append('file_ab_1', files.file_ab_1);
  if (files.file_ab_2 !== null) formData.append('file_ab_2', files.file_ab_2);
  if (files.file_cd_1 !== null) formData.append('file_cd_1', files.file_cd_1);
  if (files.file_cd_2 !== null) formData.append('file_cd_2', files.file_cd_2);

  const response = await apiClient.post<WeeklyReportApiResponse>(
    '/v1/weekly-report/generate',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );

  return response.data.result_text;
}

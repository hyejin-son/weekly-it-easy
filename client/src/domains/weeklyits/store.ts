/**
 * WeeklyIts 도메인 Zustand 스토어
 *
 * @example
 * const { reportDate, isExtracting, extractReport, generateReport } = useWeeklyReportStore();
 */

import { create } from 'zustand';
import type { WeeklyReportFiles, WeeklyReportRecord, WeeklyReportState } from './types';
import { extractWeeklyReport, generateWeeklyReport } from './api';

interface WeeklyReportStoreState extends WeeklyReportState {
  // 액션
  setReportDate: (date: string) => void;
  setFile: (key: keyof WeeklyReportFiles, file: File | null) => void;
  clearFiles: () => void;
  extractReport: () => Promise<void>;
  generateReport: () => Promise<void>;
}

const initialFiles: WeeklyReportFiles = {
  file_ab_1: null,
  file_ab_2: null,
  file_cd_1: null,
  file_cd_2: null,
};

export const useWeeklyReportStore = create<WeeklyReportStoreState>((set, get) => ({
  // 초기 상태 — Step 1 입력
  reportDate: '',
  files: { ...initialFiles },
  // 초기 상태 — Step 1 결과
  extractedRecords: [],
  isExtracted: false,
  isExtracting: false,
  // 초기 상태 — Step 2 결과
  resultText: '',
  isGenerating: false,
  // 공통
  error: null,
  // 하위 호환 (isExtracting || isGenerating, Task 4-4 UI 개편 시 제거 예정)
  isLoading: false,

  // 액션
  setReportDate: (date: string) => set({ reportDate: date }),

  setFile: (key: keyof WeeklyReportFiles, file: File | null) =>
    set((state) => ({ files: { ...state.files, [key]: file } })),

  clearFiles: () => set({ files: { ...initialFiles } }),

  /**
   * Step 1: 파일 → 레코드 추출 (AI 없음)
   * 성공 시 extractedRecords, isExtracted 업데이트
   */
  extractReport: async () => {
    const { reportDate, files } = get();
    set({ isExtracting: true, isLoading: true, error: null, isExtracted: false });
    try {
      const extractedRecords: WeeklyReportRecord[] = await extractWeeklyReport(reportDate, files);
      set({ extractedRecords, isExtracted: true, isExtracting: false, isLoading: false });
    } catch (error: any) {
      set({ error: error.message ?? '추출 중 오류가 발생했습니다', isExtracting: false, isLoading: false });
    }
  },

  /**
   * Step 2: 레코드 → 주간보고 생성 (Gemini AI 윤문 + 포맷팅)
   * extractedRecords를 사용하므로 extractReport() 이후에 호출해야 함
   * 성공 시 resultText 업데이트
   */
  generateReport: async () => {
    const { reportDate, extractedRecords } = get();
    set({ isGenerating: true, isLoading: true, error: null });
    try {
      const resultText = await generateWeeklyReport(reportDate, extractedRecords);
      set({ resultText, isGenerating: false, isLoading: false });
    } catch (error: any) {
      set({ error: error.message ?? '생성 중 오류가 발생했습니다', isGenerating: false, isLoading: false });
    }
  },
}));

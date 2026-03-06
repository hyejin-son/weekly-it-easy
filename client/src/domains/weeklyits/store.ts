/**
 * WeeklyIts 도메인 Zustand 스토어
 *
 * @example
 * const { reportDate, isLoading, generateReport } = useWeeklyReportStore();
 */

import { create } from 'zustand';
import type { WeeklyReportFiles, WeeklyReportState } from './types';
import { generateWeeklyReport } from './api';

interface WeeklyReportStoreState extends WeeklyReportState {
  // 액션
  setReportDate: (date: string) => void;
  setFile: (key: keyof WeeklyReportFiles, file: File | null) => void;
  clearFiles: () => void;
  generateReport: () => Promise<void>;
}

const initialFiles: WeeklyReportFiles = {
  file_ab_1: null,
  file_ab_2: null,
  file_cd_1: null,
  file_cd_2: null,
};

export const useWeeklyReportStore = create<WeeklyReportStoreState>((set, get) => ({
  // 초기 상태
  reportDate: '',
  files: { ...initialFiles },
  resultText: '',
  isLoading: false,
  error: null,

  // 액션
  setReportDate: (date: string) => set({ reportDate: date }),

  setFile: (key: keyof WeeklyReportFiles, file: File | null) =>
    set((state) => ({ files: { ...state.files, [key]: file } })),

  clearFiles: () => set({ files: { ...initialFiles } }),

  generateReport: async () => {
    const { reportDate, files } = get();
    set({ isLoading: true, error: null });
    try {
      const resultText = await generateWeeklyReport(reportDate, files);
      set({ resultText, isLoading: false });
    } catch (error: any) {
      set({ error: error.message ?? '오류가 발생했습니다', isLoading: false });
    }
  },
}));

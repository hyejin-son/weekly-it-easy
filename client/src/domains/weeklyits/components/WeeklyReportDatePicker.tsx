/**
 * WeeklyReportDatePicker
 *
 * 보고 기준 날짜를 선택하는 컴포넌트.
 * 선택된 날짜는 Zustand 스토어의 setReportDate()로 반영된다.
 */

import React from 'react';
import { useWeeklyReportStore } from '../store';

export const WeeklyReportDatePicker: React.FC = () => {
  const reportDate = useWeeklyReportStore((s) => s.reportDate);
  const setReportDate = useWeeklyReportStore((s) => s.setReportDate);

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor="report-date"
        className="text-sm font-semibold text-slate-700"
      >
        보고 기준 날짜
      </label>
      <input
        id="report-date"
        type="date"
        value={reportDate}
        onChange={(e) => setReportDate(e.target.value)}
        className="w-48 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 transition-colors"
      />
      <p className="text-xs text-slate-500">
        선택한 날짜가 포함된 주(월~금)의 작업이 집계됩니다.
      </p>
    </div>
  );
};

/**
 * WeeklyItsPage
 *
 * 주간보고 자동화 메인 페이지.
 * 날짜 선택 → 파일 업로드(AB/CD) → 제출 → 결과 표시 흐름을 제공한다.
 */

import React from 'react';
import { MainLayout } from '@/core/layout';
import { useWeeklyReportStore } from '../store';
import { WeeklyReportDatePicker } from '../components/WeeklyReportDatePicker';
import { FileUploadSection } from '../components/FileUploadSection';
import { WeeklyReportResult } from '../components/WeeklyReportResult';

export const WeeklyItsPage: React.FC = () => {
  const files = useWeeklyReportStore((s) => s.files);
  const isLoading = useWeeklyReportStore((s) => s.isLoading);
  const error = useWeeklyReportStore((s) => s.error);
  const generateReport = useWeeklyReportStore((s) => s.generateReport);

  const allFilesSelected =
    files.file_ab_1 !== null &&
    files.file_ab_2 !== null &&
    files.file_cd_1 !== null &&
    files.file_cd_2 !== null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (allFilesSelected && !isLoading) {
      generateReport();
    }
  };

  return (
    <MainLayout>
      <div className="mx-auto max-w-2xl px-4 py-8">
        {/* 페이지 헤더 */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">주간보고 자동화</h1>
          <p className="mt-1 text-sm text-slate-500">
            날짜와 엑셀 파일 4개를 업로드하면 주간보고 텍스트를 자동 생성합니다.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {/* 날짜 선택 */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <WeeklyReportDatePicker />
          </section>

          {/* 파일 업로드 */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-sm font-bold text-slate-700">엑셀 파일 업로드</h2>
            <FileUploadSection />
          </section>

          {/* 파일 선택 안내 */}
          {!allFilesSelected && (
            <p className="text-center text-xs text-slate-400">
              4개 파일을 모두 선택해야 제출할 수 있습니다.
            </p>
          )}

          {/* 제출 버튼 */}
          <button
            type="submit"
            disabled={!allFilesSelected || isLoading}
            className={`flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold shadow-sm transition-all duration-200 ${
              allFilesSelected && !isLoading
                ? 'bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800'
                : 'cursor-not-allowed bg-slate-200 text-slate-400'
            }`}
          >
            {isLoading ? (
              <>
                <svg
                  className="h-4 w-4 animate-spin text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                  />
                </svg>
                처리 중...
              </>
            ) : (
              '주간보고 생성'
            )}
          </button>
        </form>

        {/* 에러 메시지 */}
        {error && (
          <div
            role="alert"
            className="mt-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="mt-0.5 h-5 w-5 shrink-0 text-red-500"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM8.28 7.22a.75.75 0 0 0-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 1 0 1.06 1.06L10 11.06l1.72 1.72a.75.75 0 1 0 1.06-1.06L11.06 10l1.72-1.72a.75.75 0 0 0-1.06-1.06L10 8.94 8.28 7.22Z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <p className="text-sm font-semibold text-red-700">오류가 발생했습니다</p>
              <p className="mt-0.5 text-sm text-red-600">{error}</p>
            </div>
          </div>
        )}

        {/* 결과 표시 */}
        <div className="mt-6">
          <WeeklyReportResult />
        </div>
      </div>
    </MainLayout>
  );
};

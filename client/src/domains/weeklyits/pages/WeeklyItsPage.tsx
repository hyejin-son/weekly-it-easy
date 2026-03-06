/**
 * WeeklyItsPage
 *
 * 주간보고 자동화 메인 페이지 — 2-Step UX
 *
 * Step 1: 날짜 + 파일 업로드 → "데이터 추출" → 레코드 추출 (AI 없음)
 * Step 2: 미리보기 테이블 확인 → "주간보고 생성 (AI 윤문)" → 최종 텍스트 생성
 * Result: 결과 텍스트 복사
 */

import React from 'react';
import { MainLayout } from '@/core/layout';
import { useWeeklyReportStore } from '../store';
import { WeeklyReportDatePicker } from '../components/WeeklyReportDatePicker';
import { FileUploadSection } from '../components/FileUploadSection';
import { WeeklyReportResult } from '../components/WeeklyReportResult';
import { WeeklyReportPreviewTable } from '../components/WeeklyReportPreviewTable';

/** 공통 스피너 SVG */
const Spinner: React.FC = () => (
  <svg
    className="h-4 w-4 animate-spin"
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
);

export const WeeklyItsPage: React.FC = () => {
  const files = useWeeklyReportStore((s) => s.files);
  const isExtracting = useWeeklyReportStore((s) => s.isExtracting);
  const isExtracted = useWeeklyReportStore((s) => s.isExtracted);
  const extractedRecords = useWeeklyReportStore((s) => s.extractedRecords);
  const isGenerating = useWeeklyReportStore((s) => s.isGenerating);
  const resultText = useWeeklyReportStore((s) => s.resultText);
  const error = useWeeklyReportStore((s) => s.error);
  const extractReport = useWeeklyReportStore((s) => s.extractReport);
  const generateReport = useWeeklyReportStore((s) => s.generateReport);

  const allFilesSelected =
    files.file_ab_1 !== null &&
    files.file_ab_2 !== null &&
    files.file_cd_1 !== null &&
    files.file_cd_2 !== null;

  const canExtract = allFilesSelected && !isExtracting;
  const canGenerate = !isGenerating;

  return (
    <MainLayout>
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* 페이지 헤더 */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">주간보고 자동화</h1>
          <p className="mt-1 text-sm text-slate-500">
            날짜와 엑셀 파일 4개를 업로드하여 데이터를 추출한 후, AI 윤문으로 주간보고 텍스트를 생성합니다.
          </p>
        </div>

        {/* ===== STEP 1: 입력 영역 ===== */}
        <div className="flex flex-col gap-6">
          {/* Step 1 헤더 */}
          <div className="flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
              1
            </span>
            <h2 className="text-base font-bold text-slate-800">날짜 및 파일 업로드</h2>
          </div>

          {/* 날짜 선택 */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <WeeklyReportDatePicker />
          </section>

          {/* 파일 업로드 */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-4 text-sm font-bold text-slate-700">엑셀 파일 업로드</h3>
            <FileUploadSection />
          </section>

          {/* 4개 미선택 안내 */}
          {!allFilesSelected && (
            <p className="text-center text-xs text-slate-400">
              4개 파일을 모두 선택해야 데이터를 추출할 수 있습니다.
            </p>
          )}

          {/* 데이터 추출 버튼 */}
          <button
            type="button"
            disabled={!canExtract}
            onClick={extractReport}
            className={`flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold shadow-sm transition-all duration-200 ${
              canExtract
                ? 'bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800'
                : 'cursor-not-allowed bg-slate-200 text-slate-400'
            }`}
          >
            {isExtracting ? (
              <>
                <Spinner />
                데이터 추출 중...
              </>
            ) : (
              '데이터 추출'
            )}
          </button>
        </div>

        {/* ===== STEP 2: 미리보기 + AI 생성 (isExtracted === true 시만 노출) ===== */}
        {isExtracted && (
          <div className="mt-10 flex flex-col gap-6">
            {/* Step 2 헤더 */}
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white">
                2
              </span>
              <h2 className="text-base font-bold text-slate-800">추출 결과 미리보기</h2>
              <span className="ml-1 text-sm text-slate-500">
                총{' '}
                <span className="font-semibold text-slate-700">{extractedRecords.length}</span>건
              </span>
            </div>

            {/* 미리보기 테이블 */}
            <WeeklyReportPreviewTable records={extractedRecords} />

            {/* AI 생성 버튼 */}
            <button
              type="button"
              disabled={!canGenerate}
              onClick={generateReport}
              className={`flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold shadow-sm transition-all duration-200 ${
                canGenerate
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700 active:bg-emerald-800'
                  : 'cursor-not-allowed bg-slate-200 text-slate-400'
              }`}
            >
              {isGenerating ? (
                <>
                  <Spinner />
                  AI 윤문 중...
                </>
              ) : (
                '주간보고 생성 (AI 윤문)'
              )}
            </button>
          </div>
        )}

        {/* ===== 에러 메시지 ===== */}
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

        {/* ===== STEP 3: 결과 (resultText 있을 때만 노출) ===== */}
        {resultText && (
          <div className="mt-10">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-white">
                3
              </span>
              <h2 className="text-base font-bold text-slate-800">생성 결과</h2>
            </div>
            <WeeklyReportResult />
          </div>
        )}
      </div>
    </MainLayout>
  );
};

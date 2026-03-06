/**
 * FileUploadSection
 *
 * AB 파일 2개와 CD 파일 2개를 업로드하는 영역.
 * AB/CD 영역을 배경색·테두리로 시각적으로 구분한다.
 */

import React, { useRef } from 'react';
import type { WeeklyReportFiles } from '../types';
import { useWeeklyReportStore } from '../store';

interface FileSlotProps {
  label: string;
  fileKey: keyof WeeklyReportFiles;
  file: File | null;
  onSelect: (key: keyof WeeklyReportFiles, file: File | null) => void;
  accentColor: string; // Tailwind border/text class for button
}

const FileSlot: React.FC<FileSlotProps> = ({
  label,
  fileKey,
  file,
  onSelect,
  accentColor,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    onSelect(fileKey, selected);
    // 같은 파일 재선택 허용을 위해 value 초기화
    e.target.value = '';
  };

  const handleClear = () => {
    onSelect(fileKey, null);
  };

  return (
    <div className="flex items-center gap-3">
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls"
        onChange={handleChange}
        className="hidden"
        aria-label={label}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className={`shrink-0 rounded-md border px-3 py-1.5 text-xs font-medium shadow-sm transition-colors hover:bg-opacity-80 ${accentColor}`}
      >
        {label}
      </button>
      <span className="flex-1 truncate text-sm text-slate-700">
        {file ? file.name : <span className="text-slate-400">파일 미선택</span>}
      </span>
      {file && (
        <button
          type="button"
          onClick={handleClear}
          aria-label={`${label} 초기화`}
          className="shrink-0 rounded-full p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      )}
    </div>
  );
};

export const FileUploadSection: React.FC = () => {
  const files = useWeeklyReportStore((s) => s.files);
  const setFile = useWeeklyReportStore((s) => s.setFile);

  return (
    <div className="flex flex-col gap-4">
      {/* AB 파일 영역 */}
      <div className="rounded-xl border-2 border-blue-200 bg-blue-50 p-4 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-400" />
          <h3 className="text-sm font-bold text-blue-800">AB 파일</h3>
          <span className="text-xs text-blue-500">(ITS 실적 통합 데이터)</span>
        </div>
        <div className="flex flex-col gap-2.5">
          <FileSlot
            label="AB 파일 1"
            fileKey="file_ab_1"
            file={files.file_ab_1}
            onSelect={setFile}
            accentColor="border-blue-300 bg-blue-100 text-blue-700 hover:bg-blue-200"
          />
          <FileSlot
            label="AB 파일 2"
            fileKey="file_ab_2"
            file={files.file_ab_2}
            onSelect={setFile}
            accentColor="border-blue-300 bg-blue-100 text-blue-700 hover:bg-blue-200"
          />
        </div>
      </div>

      {/* CD 파일 영역 */}
      <div className="rounded-xl border-2 border-emerald-200 bg-emerald-50 p-4 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
          <h3 className="text-sm font-bold text-emerald-800">CD 파일</h3>
          <span className="text-xs text-emerald-500">(CH 변경관리 참고 데이터)</span>
        </div>
        <div className="flex flex-col gap-2.5">
          <FileSlot
            label="CD 파일 1"
            fileKey="file_cd_1"
            file={files.file_cd_1}
            onSelect={setFile}
            accentColor="border-emerald-300 bg-emerald-100 text-emerald-700 hover:bg-emerald-200"
          />
          <FileSlot
            label="CD 파일 2"
            fileKey="file_cd_2"
            file={files.file_cd_2}
            onSelect={setFile}
            accentColor="border-emerald-300 bg-emerald-100 text-emerald-700 hover:bg-emerald-200"
          />
        </div>
      </div>
    </div>
  );
};

/**
 * WeeklyReportResult
 *
 * 생성된 주간보고 텍스트를 표시하고 클립보드 복사 기능을 제공한다.
 * ◈, ▣ 등 특수문자와 줄바꿈이 유지되도록 <pre> 태그를 사용한다.
 * resultText가 비어있으면 렌더링하지 않는다.
 */

import React, { useState } from 'react';
import { useWeeklyReportStore } from '../store';

export const WeeklyReportResult: React.FC = () => {
  const resultText = useWeeklyReportStore((s) => s.resultText);
  const [copied, setCopied] = useState(false);

  if (!resultText) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(resultText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API 미지원 환경 대비: execCommand fallback
      const el = document.createElement('textarea');
      el.value = resultText;
      el.style.position = 'fixed';
      el.style.opacity = '0';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-700">생성 결과</h2>
        <button
          type="button"
          onClick={handleCopy}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium shadow-sm transition-all duration-200 ${
            copied
              ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
              : 'bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800'
          }`}
        >
          {copied ? (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
                <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
              </svg>
              복사됨 ✓
            </>
          ) : (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
                <path d="M7 3.5A1.5 1.5 0 0 1 8.5 2h3.879a1.5 1.5 0 0 1 1.06.44l3.122 3.12A1.5 1.5 0 0 1 17 6.622V12.5a1.5 1.5 0 0 1-1.5 1.5h-1v-3.379a3 3 0 0 0-.879-2.121L10.5 5.379A3 3 0 0 0 8.379 4.5H7v-1Z" />
                <path d="M4.5 6A1.5 1.5 0 0 0 3 7.5v9A1.5 1.5 0 0 0 4.5 18h7a1.5 1.5 0 0 0 1.5-1.5v-5.879a1.5 1.5 0 0 0-.44-1.06L9.44 6.439A1.5 1.5 0 0 0 8.378 6H4.5Z" />
              </svg>
              복사
            </>
          )}
        </button>
      </div>
      <div className="relative rounded-xl border border-slate-200 bg-slate-50 shadow-inner">
        <pre
          style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
          className="p-4 text-sm leading-relaxed text-slate-800 font-sans overflow-x-auto max-h-[60vh]"
        >
          {resultText}
        </pre>
      </div>
    </div>
  );
};

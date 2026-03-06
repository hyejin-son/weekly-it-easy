/**
 * WeeklyReportPreviewTable
 *
 * Step 1 추출 결과를 8개 컬럼 테이블로 시각화한다.
 * 컬럼이 많으므로 가로 스크롤(overflow-x: auto)을 지원하며,
 * 긴 텍스트(업무시스템2, 제목)는 말줄임 처리 후 title 속성으로 전체 텍스트를 제공한다.
 */

import React from 'react';
import type { WeeklyReportRecord } from '../types';

interface Props {
  records: WeeklyReportRecord[];
}

const STATUS_BADGE: Record<string, string> = {
  완료: 'bg-green-100 text-green-700',
  진행중: 'bg-blue-100 text-blue-700',
  대기: 'bg-slate-100 text-slate-600',
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const colorClass = STATUS_BADGE[status] ?? 'bg-slate-100 text-slate-600';
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {status}
    </span>
  );
};

export const WeeklyReportPreviewTable: React.FC<Props> = ({ records }) => {
  if (records.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <p className="text-sm text-slate-400">추출된 데이터가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              요청 ID
            </th>
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              회사
            </th>
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              업무시스템
            </th>
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              업무시스템2
            </th>
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              구분
            </th>
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              진행상태
            </th>
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              일정
            </th>
            <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-slate-600">
              제목(원본)
            </th>
          </tr>
        </thead>
        <tbody>
          {records.map((record, index) => (
            <tr
              key={`${record.request_id}-${index}`}
              className={`border-b border-slate-100 last:border-b-0 ${
                index % 2 === 1 ? 'bg-slate-50/60' : 'bg-white'
              } hover:bg-indigo-50/40 transition-colors`}
            >
              {/* 요청 ID */}
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-slate-700">
                {record.request_id}
              </td>

              {/* 회사 */}
              <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-700">
                {record.company}
              </td>

              {/* 업무시스템 */}
              <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-700">
                {record.biz_system}
              </td>

              {/* 업무시스템2 — 긴 텍스트 말줄임 */}
              <td className="px-3 py-2">
                <span
                  className="block max-w-[200px] truncate text-xs text-slate-700"
                  title={record.biz_system2}
                >
                  {record.biz_system2}
                </span>
              </td>

              {/* 구분 */}
              <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-700">
                {record.category}
              </td>

              {/* 진행상태 — 배지 */}
              <td className="whitespace-nowrap px-3 py-2">
                <StatusBadge status={record.status} />
              </td>

              {/* 일정 */}
              <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-700">
                {record.schedule || <span className="text-slate-300">—</span>}
              </td>

              {/* 제목(원본) — 긴 텍스트 말줄임 */}
              <td className="px-3 py-2">
                <span
                  className="block min-w-[180px] max-w-[280px] truncate text-xs text-slate-700"
                  title={record.title_raw}
                >
                  {record.title_raw}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

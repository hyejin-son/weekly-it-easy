/**
 * WeeklyItsPage
 *
 * WeeklyIts 서비스의 메인 페이지
 *
 * @example
 * <Route path="/" element={<WeeklyItsPage />} />
 */

import React from 'react';
import { MainLayout } from '@/core/layout';

export const WeeklyItsPage: React.FC = () => {
  return (
    <MainLayout>
      <div>WeeklyIts 메인 페이지</div>
    </MainLayout>
  );
};

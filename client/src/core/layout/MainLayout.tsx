/**
 * MainLayout Component (Skeleton)
 *
 * 메인 레이아웃 - Header, Sidebar, Content 영역 구성
 *
 * @example
 * <MainLayout>
 *   <YourPageComponent />
 * </MainLayout>
 */

import React from 'react';

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-slate-50">
      <main className="w-full">
        {children}
      </main>
    </div>
  );
};

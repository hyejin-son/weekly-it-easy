import { Routes, Route } from 'react-router-dom';
import { LoadingOverlay } from './core/loading';
import { WeeklyItsPage } from './domains/weeklyits/pages';
import { GuidePage } from './domains/guide/pages';

function App() {
  return (
    <>
      <LoadingOverlay />
      <Routes>
        <Route path="/" element={<WeeklyItsPage />} />
        <Route path="/guide" element={<GuidePage />} />
      </Routes>
    </>
  );
}

export default App;

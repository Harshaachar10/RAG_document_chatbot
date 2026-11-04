import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { DoctorDetailPage } from '../pages/DoctorDetailPage';
import { GoldenRecordsPage } from '../pages/GoldenRecordsPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { OverviewPage } from '../pages/OverviewPage';
import { QualityPage } from '../pages/QualityPage';
import { ReviewDetailPage } from '../pages/ReviewDetailPage';
import { ReviewsPage } from '../pages/ReviewsPage';
import { SourcesPage } from '../pages/SourcesPage';

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/golden-records" element={<GoldenRecordsPage />} />
        <Route path="/golden-records/:doctorId" element={<DoctorDetailPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/reviews/:reviewId" element={<ReviewDetailPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/quality" element={<QualityPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

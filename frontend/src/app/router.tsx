import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { DoctorDetailPage } from '../pages/DoctorDetailPage';
import { GoldenRecordsPage } from '../pages/GoldenRecordsPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { OverviewPage } from '../pages/OverviewPage';
import { ReviewsPage } from '../pages/ReviewsPage';

function LegacyDoctorRedirect() {
  const { doctorId = '' } = useParams();
  return <Navigate to={`/doctors/${doctorId}`} replace />;
}

function LegacyReviewRedirect() {
  const { reviewId = '' } = useParams();
  return <Navigate to={`/review?case=${encodeURIComponent(reviewId)}`} replace />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/overview" element={<Navigate to="/" replace />} />
        <Route path="/doctors" element={<GoldenRecordsPage />} />
        <Route path="/doctors/:doctorId" element={<DoctorDetailPage />} />
        <Route path="/review" element={<ReviewsPage />} />
        <Route path="/review/payments" element={<Navigate to="/review?filter=compliance" replace />} />
        <Route path="/review/changes" element={<Navigate to="/review?filter=proposed" replace />} />
        <Route path="/review/:reviewId" element={<LegacyReviewRedirect />} />
        <Route path="/golden-records" element={<Navigate to="/doctors" replace />} />
        <Route path="/golden-records/:doctorId" element={<LegacyDoctorRedirect />} />
        <Route path="/reviews" element={<Navigate to="/review" replace />} />
        <Route path="/reviews/:reviewId" element={<LegacyReviewRedirect />} />
        <Route path="/payment-compliance" element={<Navigate to="/review?filter=compliance" replace />} />
        <Route path="/notes-insights" element={<Navigate to="/review" replace />} />
        <Route path="/add-data" element={<Navigate to="/?upload=1" replace />} />
        <Route path="/add-data/history" element={<Navigate to="/?upload=1" replace />} />
        <Route path="/upload" element={<Navigate to="/?upload=1" replace />} />
        <Route path="/sources" element={<Navigate to="/?section=sources" replace />} />
        <Route path="/audit/sources" element={<Navigate to="/?section=sources" replace />} />
        <Route path="/audit/profiles" element={<Navigate to="/?how=profiles" replace />} />
        <Route path="/audit/runs" element={<Navigate to="/?how=runs" replace />} />
        <Route path="/audit/quality" element={<Navigate to="/?how=quality" replace />} />
        <Route path="/audit/log" element={<Navigate to="/?how=audit" replace />} />
        <Route path="/quality" element={<Navigate to="/?how=quality" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

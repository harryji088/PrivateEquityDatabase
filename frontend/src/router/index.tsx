import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from '../components/layout/AppLayout';
import Dashboard from '../pages/Dashboard';
import FundList from '../pages/Funds/FundList';
import FundDetail from '../pages/Funds/FundDetail';
import NavManagement from '../pages/NavData';
import PerformanceAnalytics from '../pages/Analytics/Performance';
import RiskAnalytics from '../pages/Analytics/Risk';
import Comparison from '../pages/Comparison';
import ImportExport from '../pages/ImportExport';
import Reports from '../pages/Reports';

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'funds', element: <FundList /> },
      { path: 'funds/:id', element: <FundDetail /> },
      { path: 'nav', element: <NavManagement /> },
      { path: 'analytics/performance', element: <PerformanceAnalytics /> },
      { path: 'analytics/risk', element: <RiskAnalytics /> },
      { path: 'comparison', element: <Comparison /> },
      { path: 'import-export', element: <ImportExport /> },
      { path: 'reports', element: <Reports /> },
    ],
  },
]);

export default router;

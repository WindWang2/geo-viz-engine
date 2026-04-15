import { createBrowserRouter } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import MapHomePage from './pages/MapHomePage';
import WellTablePage from './pages/WellTablePage';

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <MapHomePage /> },
      { path: 'table', element: <WellTablePage /> },
    ],
  },
]);

export default router;

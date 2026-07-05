import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import Landing from './pages/Landing';
import Login from './pages/Login';
import DashboardSidebar from './pages/DashboardSidebar';
import History from './pages/History';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<DashboardSidebar />} />
          <Route path="/dashboard/:vin" element={<DashboardSidebar />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

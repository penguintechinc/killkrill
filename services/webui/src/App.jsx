import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import Dashboard from './pages/Dashboard';
import Sensors from './pages/Sensors';
import Fleet from './pages/Fleet';
import Infrastructure from './pages/Infrastructure';
import AIAnalysis from './pages/AIAnalysis';
import Logs from './pages/Logs';
import Metrics from './pages/Metrics';
import Settings from './pages/Settings';
import Login from './pages/Login';

const queryClient = new QueryClient();

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-dark-grey">
        <div className="text-gold">Loading...</div>
      </div>
    );
  }

  return isAuthenticated() ? children : <Navigate to="/login" replace />;
};

const AppLayout = ({ children }) => {
  return (
    <div className="flex min-h-screen bg-dark-grey text-white">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <Routes>
            <Route path="/login" element={<Login />} />

            <Route path="/" element={
              <ProtectedRoute>
                <AppLayout>
                  <Dashboard />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/sensors" element={
              <ProtectedRoute>
                <AppLayout>
                  <Sensors />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/fleet" element={
              <ProtectedRoute>
                <AppLayout>
                  <Fleet />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/infrastructure" element={
              <ProtectedRoute>
                <AppLayout>
                  <Infrastructure />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/ai-analysis" element={
              <ProtectedRoute>
                <AppLayout>
                  <AIAnalysis />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/logs" element={
              <ProtectedRoute>
                <AppLayout>
                  <Logs />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/metrics" element={
              <ProtectedRoute>
                <AppLayout>
                  <Metrics />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/settings" element={
              <ProtectedRoute>
                <AppLayout>
                  <Settings />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="*" element={<NotFound />} />
          </Routes>
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-dark-grey">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gold mb-4">404</h1>
        <p className="text-gray-300">Page not found</p>
      </div>
    </div>
  );
}

export default App;

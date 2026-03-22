import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import LoginPage from "@/pages/LoginPage";
import ProjectListPage from "@/pages/ProjectListPage";
import AppShell from "@/pages/AppShell";
import DesignReference from "@/pages/DesignReference";
import UniversalTemplate from "@/pages/UniversalTemplate";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-vellum" />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { user, loading } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={
          loading ? <div className="min-h-screen bg-vellum" /> :
          user ? <Navigate to="/projects" replace /> :
          <LoginPage />
        }
      />
      <Route path="/projects" element={
        <ProtectedRoute><ProjectListPage /></ProtectedRoute>
      } />
      <Route path="/project/:projectId" element={
        <ProtectedRoute><AppShell /></ProtectedRoute>
      } />
      {/* Dev routes — preserve during development */}
      <Route path="/design" element={<DesignReference />} />
      <Route path="/template" element={<UniversalTemplate />} />
      <Route path="/" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

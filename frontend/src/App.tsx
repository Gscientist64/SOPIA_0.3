import { BrowserRouter as Router, Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import MainLayout from "./layouts/MainLayout";
import Admin from "./pages/Admin";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import Exams from "./pages/Exams";
import Interviews from "./pages/Interviews";
import Learn from "./pages/Learn";
import Login from "./pages/Login";
import Progress from "./pages/Progress";
import Register from "./pages/Register";
import { AuthProvider } from "./stores/auth";
import { ConversationsProvider } from "./stores/conversations";

function App() {
  return (
    <AuthProvider>
      <ConversationsProvider>
        <Router>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              {/* Opens straight into the assistant: no sign-in wall. */}
              <Route index element={<Navigate to="/chat" replace />} />
              <Route path="chat" element={<Chat />} />
              <Route path="interviews" element={<Interviews />} />
              {/* A registered account is needed for progress and assessments. */}
              <Route
                path="learn"
                element={
                  <ProtectedRoute memberOnly>
                    <Learn />
                  </ProtectedRoute>
                }
              />
              <Route
                path="exams"
                element={
                  <ProtectedRoute memberOnly>
                    <Exams />
                  </ProtectedRoute>
                }
              />
              <Route
                path="progress"
                element={
                  <ProtectedRoute memberOnly>
                    <Progress />
                  </ProtectedRoute>
                }
              />
              {/* Administrators only. */}
              <Route
                path="dashboard"
                element={
                  <ProtectedRoute memberOnly>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="documents"
                element={
                  <ProtectedRoute adminOnly>
                    <Documents />
                  </ProtectedRoute>
                }
              />
              <Route
                path="admin"
                element={
                  <ProtectedRoute adminOnly>
                    <Admin />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </Router>
      </ConversationsProvider>
    </AuthProvider>
  );
}

export default App;


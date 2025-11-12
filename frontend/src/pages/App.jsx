import React, { useState, useEffect } from "react";
import { Routes, Route, Link, useNavigate } from "react-router-dom";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { getMe, removeToken } from "../services/api";
import Login from "./Login";
import Register from "./Register";
import Landing from "./Landing";
import Upload from "./Upload";
import ChatNew from "./ChatNew";
import Admin from "./Admin";
import Settings from "./Settings";
import Card from "../components/Card";
import Button from "../components/Button";

function Home() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => {
          removeToken();
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [navigate]);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Landing />;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-800 mb-2">
            Xin chào, <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-blue-600">
              {user.full_name || user.email}
            </span>!
          </h1>
          {user.is_admin && (
            <span className="inline-block px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
              👑 Quản trị viên
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white hover:shadow-xl transition-all">
            <Link to="/upload" className="block">
              <div className="text-4xl mb-3">📤</div>
              <h3 className="text-xl font-bold mb-2">Upload Tài liệu</h3>
              <p className="text-blue-100 text-sm">Tải lên và quản lý tài liệu học tập của bạn</p>
            </Link>
          </Card>

          <Card className="bg-gradient-to-br from-purple-500 to-purple-600 text-white hover:shadow-xl transition-all">
            <Link to="/chat" className="block">
              <div className="text-4xl mb-3">💬</div>
              <h3 className="text-xl font-bold mb-2">Chat với AI</h3>
              <p className="text-purple-100 text-sm">Đặt câu hỏi và nhận câu trả lời thông minh</p>
            </Link>
          </Card>

        </div>

        <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200">
          <div className="flex items-start">
            <div className="text-4xl mr-4">✨</div>
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Bắt đầu học tập thông minh</h3>
              <p className="text-gray-600 mb-4">
                Upload tài liệu của bạn, sau đó đặt câu hỏi để nhận được câu trả lời chính xác dựa trên nội dung tài liệu.
              </p>
              <div className="flex flex-wrap gap-2">
                <Link to="/upload">
                  <Button variant="primary">Upload Tài liệu</Button>
                </Link>
                <Link to="/chat">
                  <Button variant="secondary">Bắt đầu Chat</Button>
                </Link>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function Navigation({ user, onLogout }) {
  return (
    <nav className="bg-white shadow-lg border-b border-gray-200 fixed top-0 left-0 right-0 z-50 backdrop-blur-sm bg-white/95">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center space-x-2 group">
              <span className="text-2xl">🧠</span>
              <span className="text-xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent group-hover:from-purple-700 group-hover:to-blue-700 transition-all">
                AI Study QnA
              </span>
            </Link>
            {user && (
              <div className="hidden md:flex items-center space-x-6">
                <Link 
                  to="/upload" 
                  className="text-gray-700 hover:text-purple-600 transition-colors font-medium text-sm"
                >
                  Upload
                </Link>
                <Link 
                  to="/chat" 
                  className="text-gray-700 hover:text-purple-600 transition-colors font-medium text-sm"
                >
                  Chat
                </Link>
                <Link 
                  to="/settings" 
                  className="text-gray-700 hover:text-purple-600 transition-colors font-medium text-sm"
                >
                  Cài đặt
                </Link>
                {user.is_admin && (
                  <Link 
                    to="/admin" 
                    className="text-gray-700 hover:text-purple-600 transition-colors font-medium text-sm"
                  >
                    Admin
                  </Link>
                )}
              </div>
            )}
          </div>
          {user ? (
            <div className="flex items-center space-x-4">
              <div className="hidden sm:block text-right">
                <div className="text-sm font-medium text-gray-700">{user.email}</div>
                {user.is_admin && (
                  <div className="text-xs text-green-600 font-medium">👑 Admin</div>
                )}
              </div>
              <Button
                onClick={onLogout}
                variant="secondary"
                className="text-sm py-2 px-4"
              >
                Đăng xuất
              </Button>
            </div>
          ) : (
            <div className="flex items-center space-x-3">
              <Link to="/login">
                <Button variant="secondary" className="text-sm">Đăng nhập</Button>
              </Link>
              <Link to="/login">
                <Button className="text-sm bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700">
                  Bắt đầu
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => {
          removeToken();
        });
    }
  }, []);

  const handleLogout = () => {
    removeToken();
    setUser(null);
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation user={user} onLogout={handleLogout} />
      <div className="pb-8 pt-20">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <Upload />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <ChatNew />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdmin={true}>
                <Admin />
              </ProtectedRoute>
            }
          />
        </Routes>
      </div>
    </div>
  );
}

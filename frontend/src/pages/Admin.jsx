import React, { useEffect, useState } from "react";
import {
  fetchAdminUsers,
  fetchAdminDocuments,
  fetchAdminStats,
  createAdminUser,
  updateAdminUser,
  deleteAdminUser,
} from "../services/api";
import Card from "../components/Card";

export default function Admin() {
  const [users, setUsers] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // User CRUD state
  const [showUserForm, setShowUserForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    full_name: "",
    is_admin: false,
  });
  const [formError, setFormError] = useState(null);
  const [formLoading, setFormLoading] = useState(false);

  const loadData = async () => {
    try {
      const [usersData, documentsData, statsData] = await Promise.all([
        fetchAdminUsers(),
        fetchAdminDocuments(),
        fetchAdminStats(),
      ]);
      setUsers(usersData);
      setDocuments(documentsData);
      setStats(statsData);
      setError(null);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateUser = () => {
    setEditingUser(null);
    setFormData({
      email: "",
      password: "",
      full_name: "",
      is_admin: false,
    });
    setFormError(null);
    setShowUserForm(true);
  };

  const handleEditUser = (user) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: "", // Don't pre-fill password
      full_name: user.full_name || "",
      is_admin: user.is_admin || false,
    });
    setFormError(null);
    setShowUserForm(true);
  };

  const handleDeleteUser = async (userId, userEmail) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa người dùng "${userEmail}"?`)) {
      return;
    }

    try {
      await deleteAdminUser(userId);
      await loadData(); // Reload data
      setError(null);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Lỗi khi xóa người dùng");
    }
  };

  const handleSubmitForm = async (e) => {
    e.preventDefault();
    setFormError(null);
    setFormLoading(true);

    try {
      if (editingUser) {
        // Update user - only send fields that are provided
        const updateData = {};
        if (formData.email !== editingUser.email) {
          updateData.email = formData.email;
        }
        if (formData.password) {
          updateData.password = formData.password;
        }
        if (formData.full_name !== (editingUser.full_name || "")) {
          updateData.full_name = formData.full_name;
        }
        if (formData.is_admin !== editingUser.is_admin) {
          updateData.is_admin = formData.is_admin;
        }

        await updateAdminUser(editingUser.id, updateData);
      } else {
        // Create user
        if (!formData.password) {
          setFormError("Mật khẩu là bắt buộc");
          setFormLoading(false);
          return;
        }
        await createAdminUser(formData);
      }

      setShowUserForm(false);
      await loadData(); // Reload data
      setFormError(null);
    } catch (err) {
      setFormError(err?.response?.data?.detail || err.message || "Lỗi khi lưu người dùng");
    } finally {
      setFormLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">Đang tải dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <h2 className="text-2xl font-bold text-gray-800 mb-4">Admin Dashboard</h2>
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg mb-4">
            {error}
          </div>
          <p className="text-gray-600">
            Hãy chắc chắn bạn đã đăng nhập bằng tài khoản admin và token được lưu trong localStorage.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <div className="mb-8">
        <div className="flex items-center mb-2">
          <span className="text-4xl mr-3">👑</span>
          <h2 className="text-4xl font-bold text-gray-800">Admin Dashboard</h2>
        </div>
        <p className="text-gray-600 ml-12">Quản lý hệ thống, người dùng và tài liệu</p>
      </div>

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Tổng người dùng</p>
                <p className="text-2xl font-bold text-gray-800">{stats.total_users}</p>
              </div>
              <div className="text-3xl">👥</div>
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Tổng tài liệu</p>
                <p className="text-2xl font-bold text-gray-800">{stats.total_documents}</p>
              </div>
              <div className="text-3xl">📄</div>
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Tổng lượt hỏi đáp</p>
                <p className="text-2xl font-bold text-gray-800">{stats.total_histories}</p>
              </div>
              <div className="text-3xl">💬</div>
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Hỏi đáp 7 ngày</p>
                <p className="text-2xl font-bold text-gray-800">{stats.recent_questions}</p>
              </div>
              <div className="text-3xl">📊</div>
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Người dùng hoạt động (7d)</p>
                <p className="text-2xl font-bold text-gray-800">{stats.active_users_7d}</p>
              </div>
              <div className="text-3xl">⚡</div>
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Dung lượng tài liệu</p>
                <p className="text-2xl font-bold text-gray-800">
                  {(stats.total_storage_bytes / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
              <div className="text-3xl">💾</div>
            </div>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xl font-semibold text-gray-800">Người dùng</h3>
            <button
              onClick={handleCreateUser}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm font-medium"
            >
              + Thêm người dùng
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase">Email</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase">Họ tên</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Docs</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Q&A</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Admin</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-900">{user.email}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{user.full_name || "-"}</td>
                    <td className="px-4 py-2 text-sm text-center">{user.documents_count}</td>
                    <td className="px-4 py-2 text-sm text-center">{user.histories_count}</td>
                    <td className="px-4 py-2 text-center">
                      {user.is_admin ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">Yes</span>
                      ) : (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">No</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <div className="flex justify-center gap-2">
                        <button
                          onClick={() => handleEditUser(user)}
                          className="px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 text-xs"
                          title="Sửa"
                        >
                          ✏️
                        </button>
                        <button
                          onClick={() => handleDeleteUser(user.id, user.email)}
                          className="px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200 text-xs"
                          title="Xóa"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Tài liệu gần đây</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase">File</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase">Owner</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Size</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Embedded</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-900 truncate max-w-xs">{doc.filename}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{doc.owner_email || "-"}</td>
                    <td className="px-4 py-2 text-sm text-center">
                      {doc.file_size ? `${(doc.file_size / (1024 * 1024)).toFixed(2)} MB` : "-"}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {doc.is_embedded ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">Yes</span>
                      ) : (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* User Form Modal */}
      {showUserForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold text-gray-800">
                  {editingUser ? "Sửa người dùng" : "Thêm người dùng mới"}
                </h3>
                <button
                  onClick={() => {
                    setShowUserForm(false);
                    setFormError(null);
                  }}
                  className="text-gray-500 hover:text-gray-700 text-2xl"
                >
                  ×
                </button>
              </div>

              {formError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                  {formError}
                </div>
              )}

              <form onSubmit={handleSubmitForm}>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder="user@example.com"
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {editingUser ? "Mật khẩu mới (để trống nếu không đổi)" : "Mật khẩu"} 
                    {!editingUser && <span className="text-red-500">*</span>}
                  </label>
                  <input
                    type="password"
                    required={!editingUser}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder="••••••••"
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Họ tên
                  </label>
                  <input
                    type="text"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder="Nguyễn Văn A"
                  />
                </div>

                <div className="mb-6">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.is_admin}
                      onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
                      className="mr-2 w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                    />
                    <span className="text-sm font-medium text-gray-700">Quyền quản trị viên</span>
                  </label>
                </div>

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setShowUserForm(false);
                      setFormError(null);
                    }}
                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                    disabled={formLoading}
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={formLoading}
                  >
                    {formLoading ? "Đang lưu..." : editingUser ? "Cập nhật" : "Tạo mới"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


import React, { useEffect, useState } from "react";
import {
  fetchAdminUsers,
  fetchAdminDocuments,
  fetchAdminStats,
} from "../services/api";
import Card from "../components/Card";

export default function Admin() {
  const [users, setUsers] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [usersData, documentsData, statsData] = await Promise.all([
          fetchAdminUsers(),
          fetchAdminDocuments(),
          fetchAdminStats(),
        ]);
        setUsers(usersData);
        setDocuments(documentsData);
        setStats(statsData);
      } catch (err) {
        setError(err?.response?.data?.detail || err.message);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

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
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Người dùng</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase">Email</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase">Họ tên</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Docs</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Q&A</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-700 uppercase">Admin</th>
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
    </div>
  );
}


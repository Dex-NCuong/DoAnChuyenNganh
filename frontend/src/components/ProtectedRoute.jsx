import React from "react";
import { Navigate } from "react-router-dom";
import { isAuthenticated } from "../utils/auth";
import { getMe } from "../services/api";

export function ProtectedRoute({ children, requireAdmin = false }) {
  const [loading, setLoading] = React.useState(true);
  const [user, setUser] = React.useState(null);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!isAuthenticated()) {
      setLoading(false);
      return;
    }

    getMe()
      .then((userData) => {
        setUser(userData);
        if (requireAdmin && !userData.is_admin) {
          setError("Admin privileges required");
        }
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || "Unauthorized");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [requireAdmin]);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  if (error || (requireAdmin && !user?.is_admin)) {
    return (
      <div style={{ padding: 16 }}>
        <h2>Access Denied</h2>
        <p>{error || "Admin privileges required"}</p>
      </div>
    );
  }

  return children;
}


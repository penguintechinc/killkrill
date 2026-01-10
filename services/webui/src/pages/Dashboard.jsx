import React, { useState, useEffect } from "react";
import { dashboardAPI } from "../services/api";
import { theme } from "../styles/theme";

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [services, setServices] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [overviewRes, servicesRes, metricsRes, activityRes] =
        await Promise.all([
          dashboardAPI.getOverview(),
          dashboardAPI.getServices(),
          dashboardAPI.getMetrics(),
          dashboardAPI.getActivity({ limit: 10 }),
        ]);

      setStats(overviewRes.data);
      setServices(servicesRes.data.services || []);
      setMetrics(metricsRes.data);
      setActivity(activityRes.data.activities || []);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
      setError(err.response?.data?.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "healthy":
      case "active":
      case "running":
        return theme.colors.status.success;
      case "warning":
      case "degraded":
        return theme.colors.status.warning;
      case "error":
      case "down":
      case "inactive":
        return theme.colors.status.error;
      default:
        return theme.colors.text.secondary;
    }
  };

  if (loading && !stats) {
    return (
      <div
        style={{
          padding: "2rem",
          backgroundColor: theme.colors.backgrounds.primary,
          minHeight: "100vh",
          color: theme.colors.text.primary,
        }}
      >
        <h1 style={{ color: theme.colors.primary.gold, marginBottom: "2rem" }}>
          Dashboard
        </h1>
        <p>Loading dashboard data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: "2rem",
          backgroundColor: theme.colors.backgrounds.primary,
          minHeight: "100vh",
        }}
      >
        <h1 style={{ color: theme.colors.primary.gold, marginBottom: "2rem" }}>
          Dashboard
        </h1>
        <div
          style={{
            padding: "1rem",
            backgroundColor: theme.colors.backgrounds.secondary,
            border: `1px solid ${theme.colors.status.error}`,
            borderRadius: theme.borderRadius.md,
            color: theme.colors.status.error,
          }}
        >
          {error}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: "2rem",
        backgroundColor: theme.colors.backgrounds.primary,
        minHeight: "100vh",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "2rem",
        }}
      >
        <h1 style={{ color: theme.colors.primary.gold, margin: 0 }}>
          Dashboard
        </h1>
        <button
          onClick={fetchDashboardData}
          style={{
            ...theme.components.button.secondary,
            padding: "8px 16px",
          }}
          onMouseEnter={(e) => {
            e.target.style.borderColor = theme.colors.primary.gold;
            e.target.style.boxShadow =
              theme.components.button.secondaryHover.boxShadow;
          }}
          onMouseLeave={(e) => {
            e.target.style.borderColor = theme.colors.borders.medium;
            e.target.style.boxShadow = "none";
          }}
        >
          Refresh
        </button>
      </div>

      {/* Stats Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
          gap: "1.5rem",
          marginBottom: "2rem",
        }}
      >
        {stats &&
          [
            {
              label: "Active Agents",
              value: stats.activeAgents || 0,
              total: stats.totalAgents || 0,
              change: stats.agentChange,
            },
            {
              label: "Total Checks",
              value: stats.totalChecks || 0,
              change: stats.checkChange,
            },
            {
              label: "System Health",
              value: stats.systemHealth ? `${stats.systemHealth}%` : "0%",
              change: stats.healthChange,
            },
            {
              label: "Active Alerts",
              value: stats.activeAlerts || 0,
              change: stats.alertChange,
            },
          ].map((stat, idx) => (
            <div
              key={idx}
              style={{
                ...theme.components.card,
                background: theme.gradients.primary,
                transition: theme.transitions.base,
              }}
            >
              <p
                style={{
                  color: theme.colors.text.secondary,
                  fontSize: theme.typography.fontSize.sm,
                  marginBottom: "0.5rem",
                }}
              >
                {stat.label}
              </p>
              <h2
                style={{
                  color: theme.colors.primary.gold,
                  fontSize: theme.typography.fontSize.xxxl,
                  margin: "0.5rem 0",
                  fontWeight: theme.typography.fontWeight.bold,
                }}
              >
                {typeof stat.value === "number"
                  ? formatNumber(stat.value)
                  : stat.value}
                {stat.total && (
                  <span
                    style={{
                      fontSize: theme.typography.fontSize.lg,
                      color: theme.colors.text.tertiary,
                    }}
                  >
                    {" "}
                    / {stat.total}
                  </span>
                )}
              </h2>
              {stat.change && (
                <p
                  style={{
                    color: stat.change.startsWith("+")
                      ? theme.colors.status.success
                      : theme.colors.status.error,
                    fontSize: theme.typography.fontSize.sm,
                    fontWeight: theme.typography.fontWeight.medium,
                  }}
                >
                  {stat.change}
                </p>
              )}
            </div>
          ))}
      </div>

      {/* Services Status */}
      <div
        style={{
          ...theme.components.card,
          marginBottom: "2rem",
          background: theme.gradients.primary,
        }}
      >
        <h2
          style={{
            color: theme.colors.primary.gold,
            marginBottom: "1.5rem",
            fontSize: theme.typography.fontSize.xl,
          }}
        >
          Service Status
        </h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
          }}
        >
          {services.length > 0 ? (
            services.map((service, idx) => (
              <div
                key={idx}
                style={{
                  padding: "1rem",
                  backgroundColor: theme.colors.backgrounds.secondary,
                  borderRadius: theme.borderRadius.md,
                  border: `1px solid ${theme.colors.borders.light}`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "0.5rem",
                  }}
                >
                  <span
                    style={{
                      color: theme.colors.text.primary,
                      fontSize: theme.typography.fontSize.base,
                      fontWeight: theme.typography.fontWeight.medium,
                    }}
                  >
                    {service.name}
                  </span>
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      backgroundColor: getStatusColor(service.status),
                      display: "inline-block",
                    }}
                  ></span>
                </div>
                <p
                  style={{
                    color: theme.colors.text.tertiary,
                    fontSize: theme.typography.fontSize.sm,
                    margin: 0,
                  }}
                >
                  {service.status}
                </p>
              </div>
            ))
          ) : (
            <p style={{ color: theme.colors.text.secondary }}>
              No services available
            </p>
          )}
        </div>
      </div>

      {/* System Metrics */}
      {metrics && (
        <div
          style={{
            ...theme.components.card,
            marginBottom: "2rem",
            background: theme.gradients.primary,
          }}
        >
          <h2
            style={{
              color: theme.colors.primary.gold,
              marginBottom: "1.5rem",
              fontSize: theme.typography.fontSize.xl,
            }}
          >
            System Metrics
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: "1.5rem",
            }}
          >
            {[
              { label: "CPU Usage", value: `${metrics.cpuUsage || 0}%` },
              { label: "Memory Usage", value: `${metrics.memoryUsage || 0}%` },
              { label: "Disk Usage", value: `${metrics.diskUsage || 0}%` },
              { label: "Network I/O", value: metrics.networkIO || "N/A" },
            ].map((metric, idx) => (
              <div key={idx}>
                <p
                  style={{
                    color: theme.colors.text.secondary,
                    fontSize: theme.typography.fontSize.sm,
                    marginBottom: "0.25rem",
                  }}
                >
                  {metric.label}
                </p>
                <p
                  style={{
                    color: theme.colors.primary.gold,
                    fontSize: theme.typography.fontSize.xl,
                    fontWeight: theme.typography.fontWeight.semibold,
                    margin: 0,
                  }}
                >
                  {metric.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activity */}
      <div
        style={{
          ...theme.components.card,
          background: theme.gradients.primary,
        }}
      >
        <h2
          style={{
            color: theme.colors.primary.gold,
            marginBottom: "1.5rem",
            fontSize: theme.typography.fontSize.xl,
          }}
        >
          Recent Activity
        </h2>
        <div style={{ maxHeight: "400px", overflowY: "auto" }}>
          {activity.length > 0 ? (
            activity.map((item, idx) => (
              <div
                key={idx}
                style={{
                  padding: "1rem",
                  marginBottom: "0.75rem",
                  backgroundColor: theme.colors.backgrounds.secondary,
                  borderRadius: theme.borderRadius.md,
                  borderLeft: `4px solid ${getStatusColor(item.type)}`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "0.5rem",
                  }}
                >
                  <span
                    style={{
                      color: theme.colors.text.primary,
                      fontSize: theme.typography.fontSize.base,
                      fontWeight: theme.typography.fontWeight.medium,
                    }}
                  >
                    {item.title || item.message}
                  </span>
                  <span
                    style={{
                      color: theme.colors.text.tertiary,
                      fontSize: theme.typography.fontSize.sm,
                      whiteSpace: "nowrap",
                      marginLeft: "1rem",
                    }}
                  >
                    {item.timestamp
                      ? new Date(item.timestamp).toLocaleString()
                      : ""}
                  </span>
                </div>
                {item.description && (
                  <p
                    style={{
                      color: theme.colors.text.secondary,
                      fontSize: theme.typography.fontSize.sm,
                      margin: 0,
                    }}
                  >
                    {item.description}
                  </p>
                )}
              </div>
            ))
          ) : (
            <p style={{ color: theme.colors.text.secondary }}>
              No recent activity
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;

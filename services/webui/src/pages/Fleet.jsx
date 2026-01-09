import React, { useState, useEffect } from "react";

const Fleet = () => {
  const [activeTab, setActiveTab] = useState("overview");
  const [fleetStatus, setFleetStatus] = useState(null);
  const [hosts, setHosts] = useState([]);
  const [queries, setQueries] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Query form state
  const [newQuery, setNewQuery] = useState({
    name: "",
    query: "",
    description: "",
  });
  const [queryResult, setQueryResult] = useState(null);
  const [runningQuery, setRunningQuery] = useState(false);

  // Host form state
  const [newHost, setNewHost] = useState({
    hostname: "",
    platform: "",
    tags: "",
  });

  // Policy form state
  const [newPolicy, setNewPolicy] = useState({
    name: "",
    query: "",
    description: "",
    interval: 3600,
  });

  const API_BASE =
    process.env.REACT_APP_API_URL || "http://localhost:8080/api/v1";

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === "overview") {
        const res = await fetch(`${API_BASE}/fleet/status`);
        const data = await res.json();
        setFleetStatus(data);
      } else if (activeTab === "hosts") {
        const res = await fetch(`${API_BASE}/fleet/hosts`);
        const data = await res.json();
        setHosts(data.hosts || []);
      } else if (activeTab === "queries") {
        const res = await fetch(`${API_BASE}/fleet/queries`);
        const data = await res.json();
        setQueries(data.queries || []);
      } else if (activeTab === "policies") {
        const res = await fetch(`${API_BASE}/fleet/policies`);
        const data = await res.json();
        setPolicies(data.policies || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const addHost = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/fleet/hosts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hostname: newHost.hostname,
          platform: newHost.platform,
          tags: newHost.tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean),
        }),
      });
      if (res.ok) {
        setNewHost({ hostname: "", platform: "", tags: "" });
        fetchData();
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const removeHost = async (hostId) => {
    try {
      await fetch(`${API_BASE}/fleet/hosts/${hostId}`, { method: "DELETE" });
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  const createQuery = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/fleet/queries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newQuery),
      });
      if (res.ok) {
        setNewQuery({ name: "", query: "", description: "" });
        fetchData();
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const runQuery = async (queryId, queryText) => {
    setRunningQuery(true);
    setQueryResult(null);
    try {
      const res = await fetch(`${API_BASE}/fleet/queries/${queryId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryText }),
      });
      const data = await res.json();
      setQueryResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningQuery(false);
    }
  };

  const createPolicy = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/fleet/policies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newPolicy),
      });
      if (res.ok) {
        setNewPolicy({ name: "", query: "", description: "", interval: 3600 });
        fetchData();
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "hosts", label: "Hosts" },
    { id: "queries", label: "Queries" },
    { id: "policies", label: "Policies" },
  ];

  return (
    <div
      className="p-6"
      style={{ backgroundColor: "#1a1a1a", minHeight: "100vh" }}
    >
      <h1 style={{ color: "#d4af37", marginBottom: "2rem" }}>
        Fleet Management
      </h1>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "1rem",
          marginBottom: "2rem",
          borderBottom: "1px solid #333",
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "0.75rem 1.5rem",
              backgroundColor: activeTab === tab.id ? "#2a2a2a" : "transparent",
              color: activeTab === tab.id ? "#d4af37" : "#999",
              border: "none",
              borderBottom: activeTab === tab.id ? "2px solid #d4af37" : "none",
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div
          style={{
            backgroundColor: "#3a1a1a",
            color: "#ff6b6b",
            padding: "1rem",
            borderRadius: "4px",
            marginBottom: "1rem",
          }}
        >
          Error: {error}
        </div>
      )}

      {loading ? (
        <p style={{ color: "#999" }}>Loading...</p>
      ) : (
        <>
          {/* Overview Tab */}
          {activeTab === "overview" && fleetStatus && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                gap: "1.5rem",
              }}
            >
              <StatCard
                label="Total Hosts"
                value={fleetStatus.total_hosts || 0}
              />
              <StatCard
                label="Online Hosts"
                value={fleetStatus.online_hosts || 0}
              />
              <StatCard
                label="Offline Hosts"
                value={fleetStatus.offline_hosts || 0}
              />
              <StatCard
                label="Total Queries"
                value={fleetStatus.total_queries || 0}
              />
              <StatCard
                label="Active Policies"
                value={fleetStatus.active_policies || 0}
              />
              <StatCard
                label="Pending Tasks"
                value={fleetStatus.pending_tasks || 0}
              />
            </div>
          )}

          {/* Hosts Tab */}
          {activeTab === "hosts" && (
            <div>
              {/* Add Host Form */}
              <div style={cardStyle}>
                <h2 style={{ color: "#d4af37", marginBottom: "1rem" }}>
                  Add New Host
                </h2>
                <form
                  onSubmit={addHost}
                  style={{ display: "grid", gap: "1rem" }}
                >
                  <input
                    type="text"
                    placeholder="Hostname"
                    value={newHost.hostname}
                    onChange={(e) =>
                      setNewHost({ ...newHost, hostname: e.target.value })
                    }
                    style={inputStyle}
                    required
                  />
                  <input
                    type="text"
                    placeholder="Platform (linux/windows/darwin)"
                    value={newHost.platform}
                    onChange={(e) =>
                      setNewHost({ ...newHost, platform: e.target.value })
                    }
                    style={inputStyle}
                    required
                  />
                  <input
                    type="text"
                    placeholder="Tags (comma-separated)"
                    value={newHost.tags}
                    onChange={(e) =>
                      setNewHost({ ...newHost, tags: e.target.value })
                    }
                    style={inputStyle}
                  />
                  <button type="submit" style={buttonStyle}>
                    Add Host
                  </button>
                </form>
              </div>

              {/* Hosts List */}
              <div style={{ ...cardStyle, marginTop: "1.5rem" }}>
                <h2 style={{ color: "#d4af37", marginBottom: "1rem" }}>
                  Hosts ({hosts.length})
                </h2>
                <div style={{ display: "grid", gap: "1rem" }}>
                  {hosts.map((host) => (
                    <div
                      key={host.id}
                      style={{
                        backgroundColor: "#222",
                        padding: "1rem",
                        borderRadius: "4px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <h3 style={{ color: "#d4af37" }}>{host.hostname}</h3>
                        <p style={{ color: "#999", fontSize: "0.9rem" }}>
                          Platform: {host.platform} | Status:{" "}
                          {host.status || "unknown"}
                        </p>
                        {host.tags && (
                          <p style={{ color: "#666", fontSize: "0.85rem" }}>
                            Tags: {host.tags.join(", ")}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={() => removeHost(host.id)}
                        style={{ ...buttonStyle, backgroundColor: "#aa3333" }}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Queries Tab */}
          {activeTab === "queries" && (
            <div>
              {/* Create Query Form */}
              <div style={cardStyle}>
                <h2 style={{ color: "#d4af37", marginBottom: "1rem" }}>
                  Create New Query
                </h2>
                <form
                  onSubmit={createQuery}
                  style={{ display: "grid", gap: "1rem" }}
                >
                  <input
                    type="text"
                    placeholder="Query Name"
                    value={newQuery.name}
                    onChange={(e) =>
                      setNewQuery({ ...newQuery, name: e.target.value })
                    }
                    style={inputStyle}
                    required
                  />
                  <textarea
                    placeholder="SQL Query"
                    value={newQuery.query}
                    onChange={(e) =>
                      setNewQuery({ ...newQuery, query: e.target.value })
                    }
                    style={{ ...inputStyle, minHeight: "100px" }}
                    required
                  />
                  <input
                    type="text"
                    placeholder="Description"
                    value={newQuery.description}
                    onChange={(e) =>
                      setNewQuery({ ...newQuery, description: e.target.value })
                    }
                    style={inputStyle}
                  />
                  <button type="submit" style={buttonStyle}>
                    Create Query
                  </button>
                </form>
              </div>

              {/* Queries List */}
              <div style={{ ...cardStyle, marginTop: "1.5rem" }}>
                <h2 style={{ color: "#d4af37", marginBottom: "1rem" }}>
                  Saved Queries ({queries.length})
                </h2>
                <div style={{ display: "grid", gap: "1rem" }}>
                  {queries.map((query) => (
                    <div
                      key={query.id}
                      style={{
                        backgroundColor: "#222",
                        padding: "1rem",
                        borderRadius: "4px",
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
                        <h3 style={{ color: "#d4af37" }}>{query.name}</h3>
                        <button
                          onClick={() => runQuery(query.id, query.query)}
                          style={buttonStyle}
                          disabled={runningQuery}
                        >
                          {runningQuery ? "Running..." : "Run Query"}
                        </button>
                      </div>
                      <p
                        style={{
                          color: "#999",
                          fontSize: "0.9rem",
                          marginBottom: "0.5rem",
                        }}
                      >
                        {query.description}
                      </p>
                      <pre
                        style={{
                          backgroundColor: "#1a1a1a",
                          color: "#ddd",
                          padding: "0.75rem",
                          borderRadius: "4px",
                          overflow: "auto",
                          fontSize: "0.85rem",
                        }}
                      >
                        {query.query}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>

              {/* Query Results */}
              {queryResult && (
                <div style={{ ...cardStyle, marginTop: "1.5rem" }}>
                  <h2 style={{ color: "#d4af37", marginBottom: "1rem" }}>
                    Query Results
                  </h2>
                  <pre
                    style={{
                      backgroundColor: "#222",
                      color: "#ddd",
                      padding: "1rem",
                      borderRadius: "4px",
                      overflow: "auto",
                      maxHeight: "400px",
                    }}
                  >
                    {JSON.stringify(queryResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Policies Tab */}
          {activeTab === "policies" && (
            <div>
              {/* Create Policy Form */}
              <div style={cardStyle}>
                <h2 style={{ color: "#d4af37", marginBottom: "1rem" }}>
                  Create New Policy
                </h2>
                <form
                  onSubmit={createPolicy}
                  style={{ display: "grid", gap: "1rem" }}
                >
                  <input
                    type="text"
                    placeholder="Policy Name"
                    value={newPolicy.name}
                    onChange={(e) =>
                      setNewPolicy({ ...newPolicy, name: e.target.value })
                    }
                    style={inputStyle}
                    required
                  />
                  <textarea
                    placeholder="SQL Query"
                    value={newPolicy.query}
                    onChange={(e) =>
                      setNewPolicy({ ...newPolicy, query: e.target.value })
                    }
                    style={{ ...inputStyle, minHeight: "100px" }}
                    required
                  />
                  <input
                    type="text"
                    placeholder="Description"
                    value={newPolicy.description}
                    onChange={(e) =>
                      setNewPolicy({
                        ...newPolicy,
                        description: e.target.value,
                      })
                    }
                    style={inputStyle}
                  />
                  <input
                    type="number"
                    placeholder="Interval (seconds)"
                    value={newPolicy.interval}
                    onChange={(e) =>
                      setNewPolicy({
                        ...newPolicy,
                        interval: parseInt(e.target.value),
                      })
                    }
                    style={inputStyle}
                    required
                  />
                  <button type="submit" style={buttonStyle}>
                    Create Policy
                  </button>
                </form>
              </div>

              {/* Policies List */}
              <div style={{ ...cardStyle, marginTop: "1.5rem" }}>
                <h2 style={{ color: "#d4af37", marginBottom: "1rem" }}>
                  Active Policies ({policies.length})
                </h2>
                <div style={{ display: "grid", gap: "1rem" }}>
                  {policies.map((policy) => (
                    <div
                      key={policy.id}
                      style={{
                        backgroundColor: "#222",
                        padding: "1rem",
                        borderRadius: "4px",
                      }}
                    >
                      <h3 style={{ color: "#d4af37", marginBottom: "0.5rem" }}>
                        {policy.name}
                      </h3>
                      <p
                        style={{
                          color: "#999",
                          fontSize: "0.9rem",
                          marginBottom: "0.5rem",
                        }}
                      >
                        {policy.description}
                      </p>
                      <p
                        style={{
                          color: "#666",
                          fontSize: "0.85rem",
                          marginBottom: "0.5rem",
                        }}
                      >
                        Interval: {policy.interval}s | Status:{" "}
                        {policy.status || "active"}
                      </p>
                      <pre
                        style={{
                          backgroundColor: "#1a1a1a",
                          color: "#ddd",
                          padding: "0.75rem",
                          borderRadius: "4px",
                          overflow: "auto",
                          fontSize: "0.85rem",
                        }}
                      >
                        {policy.query}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

const StatCard = ({ label, value }) => (
  <div style={cardStyle}>
    <p style={{ color: "#999", fontSize: "0.9rem", marginBottom: "0.5rem" }}>
      {label}
    </p>
    <h2 style={{ color: "#d4af37", fontSize: "2rem", margin: 0 }}>{value}</h2>
  </div>
);

const cardStyle = {
  backgroundColor: "#2a2a2a",
  border: "1px solid #d4af37",
  borderRadius: "8px",
  padding: "1.5rem",
};

const inputStyle = {
  backgroundColor: "#1a1a1a",
  border: "1px solid #444",
  borderRadius: "4px",
  padding: "0.75rem",
  color: "#ddd",
  fontSize: "1rem",
};

const buttonStyle = {
  backgroundColor: "#d4af37",
  color: "#1a1a1a",
  border: "none",
  borderRadius: "4px",
  padding: "0.75rem 1.5rem",
  cursor: "pointer",
  fontWeight: "bold",
  fontSize: "1rem",
};

export default Fleet;

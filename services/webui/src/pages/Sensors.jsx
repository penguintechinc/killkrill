import React, { useState, useEffect } from "react";
import { sensorsAPI } from "../services/api";
import { theme } from "../styles/theme";
import TabContainer from "../components/layout/TabContainer";

const Sensors = () => {
  const [activeTab, setActiveTab] = useState("agents");
  const [agents, setAgents] = useState([]);
  const [checks, setChecks] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState("create");
  const [modalType, setModalType] = useState("agent");
  const [currentItem, setCurrentItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [filterType, setFilterType] = useState("all");

  const tabs = [
    { id: "agents", label: "Agents" },
    { id: "checks", label: "Checks" },
    { id: "results", label: "Results" },
  ];

  useEffect(() => {
    fetchData();
  }, [activeTab, filterType]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === "agents") {
        const res = await sensorsAPI.getAgents();
        setAgents(res.data.agents || []);
      } else if (activeTab === "checks") {
        const params = filterType !== "all" ? { type: filterType } : {};
        const res = await sensorsAPI.getChecks(params);
        setChecks(res.data.checks || []);
      } else if (activeTab === "results") {
        const params = filterType !== "all" ? { status: filterType } : {};
        const res = await sensorsAPI.getResults(params);
        setResults(res.data.results || []);
      }
    } catch (err) {
      console.error("Fetch error:", err);
      setError(err.response?.data?.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = (type) => {
    setModalMode("create");
    setModalType(type);
    setCurrentItem(null);
    setFormData(
      type === "agent"
        ? {
            name: "",
            hostname: "",
            ip_address: "",
            description: "",
          }
        : {
            name: "",
            type: "tcp",
            target: "",
            interval: 60,
            timeout: 5,
            agent_id: "",
            config: {},
          },
    );
    setShowModal(true);
  };

  const handleEdit = (item, type) => {
    setModalMode("edit");
    setModalType(type);
    setCurrentItem(item);
    setFormData(item);
    setShowModal(true);
  };

  const handleDelete = async (id, type) => {
    if (!window.confirm("Are you sure you want to delete this item?")) return;

    try {
      if (type === "agent") {
        await sensorsAPI.deleteAgent(id);
      } else {
        await sensorsAPI.deleteCheck(id);
      }
      fetchData();
    } catch (err) {
      alert(err.response?.data?.message || "Failed to delete item");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (modalType === "agent") {
        if (modalMode === "create") {
          await sensorsAPI.createAgent(formData);
        } else {
          await sensorsAPI.updateAgent(currentItem.id, formData);
        }
      } else {
        if (modalMode === "create") {
          await sensorsAPI.createCheck(formData);
        } else {
          await sensorsAPI.updateCheck(currentItem.id, formData);
        }
      }
      setShowModal(false);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.message || "Failed to save item");
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "success":
      case "active":
      case "online":
        return theme.colors.status.success;
      case "warning":
        return theme.colors.status.warning;
      case "failure":
      case "error":
      case "offline":
        return theme.colors.status.error;
      default:
        return theme.colors.text.secondary;
    }
  };

  const renderAgents = () => (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
        }}
      >
        <h2 style={{ color: theme.colors.primary.gold, margin: 0 }}>Agents</h2>
        <button
          onClick={() => handleCreate("agent")}
          style={{
            ...theme.components.button.primary,
            padding: "10px 20px",
          }}
          onMouseEnter={(e) => {
            e.target.style.boxShadow =
              theme.components.button.primaryHover.boxShadow;
            e.target.style.transform =
              theme.components.button.primaryHover.transform;
          }}
          onMouseLeave={(e) => {
            e.target.style.boxShadow =
              theme.components.button.primary.boxShadow;
            e.target.style.transform = "none";
          }}
        >
          Add Agent
        </button>
      </div>

      {loading ? (
        <p style={{ color: theme.colors.text.secondary }}>Loading agents...</p>
      ) : agents.length === 0 ? (
        <p style={{ color: theme.colors.text.secondary }}>No agents found</p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            gap: "1rem",
          }}
        >
          {agents.map((agent) => (
            <div
              key={agent.id}
              style={{
                ...theme.components.card,
                background: theme.gradients.primary,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  marginBottom: "1rem",
                }}
              >
                <div style={{ flex: 1 }}>
                  <h3
                    style={{
                      color: theme.colors.primary.gold,
                      margin: "0 0 0.5rem 0",
                      fontSize: theme.typography.fontSize.lg,
                    }}
                  >
                    {agent.name}
                  </h3>
                  <p
                    style={{
                      color: theme.colors.text.secondary,
                      fontSize: theme.typography.fontSize.sm,
                      margin: "0.25rem 0",
                    }}
                  >
                    {agent.hostname}
                  </p>
                  <p
                    style={{
                      color: theme.colors.text.tertiary,
                      fontSize: theme.typography.fontSize.sm,
                      margin: "0.25rem 0",
                    }}
                  >
                    {agent.ip_address}
                  </p>
                </div>
                <span
                  style={{
                    width: "10px",
                    height: "10px",
                    borderRadius: "50%",
                    backgroundColor: getStatusColor(agent.status),
                    display: "inline-block",
                    flexShrink: 0,
                  }}
                ></span>
              </div>

              {agent.description && (
                <p
                  style={{
                    color: theme.colors.text.secondary,
                    fontSize: theme.typography.fontSize.sm,
                    marginBottom: "1rem",
                  }}
                >
                  {agent.description}
                </p>
              )}

              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  marginTop: "1rem",
                }}
              >
                <button
                  onClick={() => handleEdit(agent, "agent")}
                  style={{
                    ...theme.components.button.secondary,
                    flex: 1,
                    padding: "8px",
                    fontSize: theme.typography.fontSize.sm,
                  }}
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(agent.id, "agent")}
                  style={{
                    ...theme.components.button.secondary,
                    flex: 1,
                    padding: "8px",
                    fontSize: theme.typography.fontSize.sm,
                    borderColor: theme.colors.status.error,
                    color: theme.colors.status.error,
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderChecks = () => (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <h2 style={{ color: theme.colors.primary.gold, margin: 0 }}>
            Checks
          </h2>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              ...theme.components.input,
              padding: "8px 12px",
              cursor: "pointer",
            }}
          >
            <option value="all">All Types</option>
            <option value="tcp">TCP</option>
            <option value="http">HTTP</option>
            <option value="dns">DNS</option>
            <option value="icmp">ICMP</option>
          </select>
        </div>
        <button
          onClick={() => handleCreate("check")}
          style={{
            ...theme.components.button.primary,
            padding: "10px 20px",
          }}
          onMouseEnter={(e) => {
            e.target.style.boxShadow =
              theme.components.button.primaryHover.boxShadow;
            e.target.style.transform =
              theme.components.button.primaryHover.transform;
          }}
          onMouseLeave={(e) => {
            e.target.style.boxShadow =
              theme.components.button.primary.boxShadow;
            e.target.style.transform = "none";
          }}
        >
          Add Check
        </button>
      </div>

      {loading ? (
        <p style={{ color: theme.colors.text.secondary }}>Loading checks...</p>
      ) : checks.length === 0 ? (
        <p style={{ color: theme.colors.text.secondary }}>No checks found</p>
      ) : (
        <div
          style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}
        >
          {checks.map((check) => (
            <div
              key={check.id}
              style={{
                ...theme.components.card,
                background: theme.gradients.primary,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "1rem",
                    marginBottom: "0.5rem",
                  }}
                >
                  <h3
                    style={{
                      color: theme.colors.primary.gold,
                      margin: 0,
                      fontSize: theme.typography.fontSize.base,
                    }}
                  >
                    {check.name}
                  </h3>
                  <span
                    style={{
                      ...theme.components.badge,
                      fontSize: theme.typography.fontSize.xs,
                    }}
                  >
                    {check.type?.toUpperCase()}
                  </span>
                </div>
                <p
                  style={{
                    color: theme.colors.text.secondary,
                    fontSize: theme.typography.fontSize.sm,
                    margin: "0.25rem 0",
                  }}
                >
                  Target: {check.target}
                </p>
                <p
                  style={{
                    color: theme.colors.text.tertiary,
                    fontSize: theme.typography.fontSize.sm,
                    margin: 0,
                  }}
                >
                  Interval: {check.interval}s | Timeout: {check.timeout}s
                </p>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  alignItems: "center",
                }}
              >
                <button
                  onClick={() => handleEdit(check, "check")}
                  style={{
                    ...theme.components.button.secondary,
                    padding: "8px 16px",
                    fontSize: theme.typography.fontSize.sm,
                  }}
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(check.id, "check")}
                  style={{
                    ...theme.components.button.secondary,
                    padding: "8px 16px",
                    fontSize: theme.typography.fontSize.sm,
                    borderColor: theme.colors.status.error,
                    color: theme.colors.status.error,
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderResults = () => (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <h2 style={{ color: theme.colors.primary.gold, margin: 0 }}>
            Results
          </h2>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              ...theme.components.input,
              padding: "8px 12px",
              cursor: "pointer",
            }}
          >
            <option value="all">All Status</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="timeout">Timeout</option>
          </select>
        </div>
        <button
          onClick={fetchData}
          style={{
            ...theme.components.button.secondary,
            padding: "8px 16px",
          }}
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <p style={{ color: theme.colors.text.secondary }}>Loading results...</p>
      ) : results.length === 0 ? (
        <p style={{ color: theme.colors.text.secondary }}>No results found</p>
      ) : (
        <div
          style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}
        >
          {results.map((result, idx) => (
            <div
              key={idx}
              style={{
                padding: "1rem",
                backgroundColor: theme.colors.backgrounds.secondary,
                borderRadius: theme.borderRadius.md,
                borderLeft: `4px solid ${getStatusColor(result.status)}`,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "1rem",
                    marginBottom: "0.5rem",
                  }}
                >
                  <span
                    style={{
                      color: theme.colors.text.primary,
                      fontWeight: theme.typography.fontWeight.medium,
                    }}
                  >
                    {result.check_name}
                  </span>
                  <span
                    style={{
                      fontSize: theme.typography.fontSize.sm,
                      color: getStatusColor(result.status),
                      fontWeight: theme.typography.fontWeight.semibold,
                      textTransform: "uppercase",
                    }}
                  >
                    {result.status}
                  </span>
                </div>
                <p
                  style={{
                    color: theme.colors.text.secondary,
                    fontSize: theme.typography.fontSize.sm,
                    margin: "0.25rem 0",
                  }}
                >
                  Response Time: {result.response_time || "N/A"}ms
                </p>
                {result.message && (
                  <p
                    style={{
                      color: theme.colors.text.tertiary,
                      fontSize: theme.typography.fontSize.sm,
                      margin: 0,
                    }}
                  >
                    {result.message}
                  </p>
                )}
              </div>
              <span
                style={{
                  color: theme.colors.text.tertiary,
                  fontSize: theme.typography.fontSize.sm,
                  whiteSpace: "nowrap",
                  marginLeft: "1rem",
                }}
              >
                {result.timestamp
                  ? new Date(result.timestamp).toLocaleString()
                  : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderModal = () => {
    if (!showModal) return null;

    return (
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0, 0, 0, 0.7)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          zIndex: 1000,
          padding: "2rem",
        }}
      >
        <div
          style={{
            backgroundColor: theme.colors.backgrounds.secondary,
            borderRadius: theme.borderRadius.lg,
            padding: "2rem",
            maxWidth: "600px",
            width: "100%",
            maxHeight: "90vh",
            overflowY: "auto",
            border: `1px solid ${theme.colors.borders.medium}`,
          }}
        >
          <h2
            style={{
              color: theme.colors.primary.gold,
              marginTop: 0,
              marginBottom: "1.5rem",
            }}
          >
            {modalMode === "create" ? "Create" : "Edit"}{" "}
            {modalType === "agent" ? "Agent" : "Check"}
          </h2>

          <form onSubmit={handleSubmit}>
            {modalType === "agent" ? (
              <>
                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    Name *
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name || ""}
                    onChange={handleInputChange}
                    required
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    Hostname *
                  </label>
                  <input
                    type="text"
                    name="hostname"
                    value={formData.hostname || ""}
                    onChange={handleInputChange}
                    required
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    IP Address *
                  </label>
                  <input
                    type="text"
                    name="ip_address"
                    value={formData.ip_address || ""}
                    onChange={handleInputChange}
                    required
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    Description
                  </label>
                  <textarea
                    name="description"
                    value={formData.description || ""}
                    onChange={handleInputChange}
                    rows={3}
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                      resize: "vertical",
                    }}
                  />
                </div>
              </>
            ) : (
              <>
                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    Name *
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name || ""}
                    onChange={handleInputChange}
                    required
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    Type *
                  </label>
                  <select
                    name="type"
                    value={formData.type || "tcp"}
                    onChange={handleInputChange}
                    required
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                      cursor: "pointer",
                    }}
                  >
                    <option value="tcp">TCP</option>
                    <option value="http">HTTP</option>
                    <option value="dns">DNS</option>
                    <option value="icmp">ICMP</option>
                  </select>
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    Target *
                  </label>
                  <input
                    type="text"
                    name="target"
                    value={formData.target || ""}
                    onChange={handleInputChange}
                    required
                    placeholder="e.g., example.com:443"
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "1rem",
                    marginBottom: "1rem",
                  }}
                >
                  <div>
                    <label
                      style={{
                        display: "block",
                        color: theme.colors.text.secondary,
                        marginBottom: "0.5rem",
                        fontSize: theme.typography.fontSize.sm,
                      }}
                    >
                      Interval (seconds) *
                    </label>
                    <input
                      type="number"
                      name="interval"
                      value={formData.interval || 60}
                      onChange={handleInputChange}
                      required
                      min="1"
                      style={{
                        ...theme.components.input,
                        width: "100%",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>

                  <div>
                    <label
                      style={{
                        display: "block",
                        color: theme.colors.text.secondary,
                        marginBottom: "0.5rem",
                        fontSize: theme.typography.fontSize.sm,
                      }}
                    >
                      Timeout (seconds) *
                    </label>
                    <input
                      type="number"
                      name="timeout"
                      value={formData.timeout || 5}
                      onChange={handleInputChange}
                      required
                      min="1"
                      style={{
                        ...theme.components.input,
                        width: "100%",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label
                    style={{
                      display: "block",
                      color: theme.colors.text.secondary,
                      marginBottom: "0.5rem",
                      fontSize: theme.typography.fontSize.sm,
                    }}
                  >
                    Agent ID *
                  </label>
                  <select
                    name="agent_id"
                    value={formData.agent_id || ""}
                    onChange={handleInputChange}
                    required
                    style={{
                      ...theme.components.input,
                      width: "100%",
                      boxSizing: "border-box",
                      cursor: "pointer",
                    }}
                  >
                    <option value="">Select Agent</option>
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name} ({agent.hostname})
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            <div
              style={{
                display: "flex",
                gap: "1rem",
                marginTop: "2rem",
              }}
            >
              <button
                type="submit"
                style={{
                  ...theme.components.button.primary,
                  flex: 1,
                  padding: "10px",
                }}
              >
                {modalMode === "create" ? "Create" : "Update"}
              </button>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                style={{
                  ...theme.components.button.secondary,
                  flex: 1,
                  padding: "10px",
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  return (
    <div
      style={{
        padding: "2rem",
        backgroundColor: theme.colors.backgrounds.primary,
        minHeight: "100vh",
      }}
    >
      <h1 style={{ color: theme.colors.primary.gold, marginBottom: "2rem" }}>
        Sensors
      </h1>

      {error && (
        <div
          style={{
            padding: "1rem",
            marginBottom: "1rem",
            backgroundColor: theme.colors.backgrounds.secondary,
            border: `1px solid ${theme.colors.status.error}`,
            borderRadius: theme.borderRadius.md,
            color: theme.colors.status.error,
          }}
        >
          {error}
        </div>
      )}

      <div
        style={{
          backgroundColor: theme.colors.backgrounds.secondary,
          border: `1px solid ${theme.colors.borders.medium}`,
          borderRadius: theme.borderRadius.lg,
          overflow: "hidden",
        }}
      >
        <TabContainer
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <div style={{ padding: "2rem" }}>
          {activeTab === "agents" && renderAgents()}
          {activeTab === "checks" && renderChecks()}
          {activeTab === "results" && renderResults()}
        </div>
      </div>

      {renderModal()}
    </div>
  );
};

export default Sensors;

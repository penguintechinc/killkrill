import React, { useState, useEffect } from 'react';

const Infrastructure = () => {
  const [activeTab, setActiveTab] = useState('prometheus');
  const [prometheusStatus, setPrometheusStatus] = useState(null);
  const [prometheusTargets, setPrometheusTargets] = useState([]);
  const [prometheusQuery, setPrometheusQuery] = useState('');
  const [prometheusResult, setPrometheusResult] = useState(null);

  const [elasticsearchStatus, setElasticsearchStatus] = useState(null);
  const [elasticsearchIndices, setElasticsearchIndices] = useState([]);
  const [elasticsearchQuery, setElasticsearchQuery] = useState('');
  const [elasticsearchResult, setElasticsearchResult] = useState(null);

  const [grafanaStatus, setGrafanaStatus] = useState(null);
  const [grafanaDashboards, setGrafanaDashboards] = useState([]);

  const [alertmanagerStatus, setAlertmanagerStatus] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [silences, setSilences] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8080/api/v1';

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'prometheus') {
        const statusRes = await fetch(`${API_BASE}/infrastructure/prometheus/status`);
        const statusData = await statusRes.json();
        setPrometheusStatus(statusData);

        const targetsRes = await fetch(`${API_BASE}/infrastructure/prometheus/targets`);
        const targetsData = await targetsRes.json();
        setPrometheusTargets(targetsData.targets || []);
      } else if (activeTab === 'elasticsearch') {
        const statusRes = await fetch(`${API_BASE}/infrastructure/elasticsearch/status`);
        const statusData = await statusRes.json();
        setElasticsearchStatus(statusData);

        const indicesRes = await fetch(`${API_BASE}/infrastructure/elasticsearch/indices`);
        const indicesData = await indicesRes.json();
        setElasticsearchIndices(indicesData.indices || []);
      } else if (activeTab === 'grafana') {
        const statusRes = await fetch(`${API_BASE}/infrastructure/grafana/status`);
        const statusData = await statusRes.json();
        setGrafanaStatus(statusData);

        const dashboardsRes = await fetch(`${API_BASE}/infrastructure/grafana/dashboards`);
        const dashboardsData = await dashboardsRes.json();
        setGrafanaDashboards(dashboardsData.dashboards || []);
      } else if (activeTab === 'alertmanager') {
        const statusRes = await fetch(`${API_BASE}/infrastructure/alertmanager/status`);
        const statusData = await statusRes.json();
        setAlertmanagerStatus(statusData);

        const alertsRes = await fetch(`${API_BASE}/infrastructure/alertmanager/alerts`);
        const alertsData = await alertsRes.json();
        setAlerts(alertsData.alerts || []);

        const silencesRes = await fetch(`${API_BASE}/infrastructure/alertmanager/silences`);
        const silencesData = await silencesRes.json();
        setSilences(silencesData.silences || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const executePrometheusQuery = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/infrastructure/prometheus/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: prometheusQuery }),
      });
      const data = await res.json();
      setPrometheusResult(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const executeElasticsearchQuery = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/infrastructure/elasticsearch/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: elasticsearchQuery }),
      });
      const data = await res.json();
      setElasticsearchResult(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const silenceAlert = async (alertId) => {
    try {
      await fetch(`${API_BASE}/infrastructure/alertmanager/silences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_id: alertId, duration: '1h' }),
      });
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  const tabs = [
    { id: 'prometheus', label: 'Prometheus' },
    { id: 'elasticsearch', label: 'Elasticsearch' },
    { id: 'grafana', label: 'Grafana' },
    { id: 'alertmanager', label: 'AlertManager' },
  ];

  return (
    <div className="p-6" style={{ backgroundColor: '#1a1a1a', minHeight: '100vh' }}>
      <h1 style={{ color: '#d4af37', marginBottom: '2rem' }}>Infrastructure Monitoring</h1>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid #333' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '0.75rem 1.5rem',
              backgroundColor: activeTab === tab.id ? '#2a2a2a' : 'transparent',
              color: activeTab === tab.id ? '#d4af37' : '#999',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid #d4af37' : 'none',
              cursor: 'pointer',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ backgroundColor: '#3a1a1a', color: '#ff6b6b', padding: '1rem', borderRadius: '4px', marginBottom: '1rem' }}>
          Error: {error}
        </div>
      )}

      {loading ? (
        <p style={{ color: '#999' }}>Loading...</p>
      ) : (
        <>
          {/* Prometheus Tab */}
          {activeTab === 'prometheus' && (
            <div>
              {/* Status */}
              {prometheusStatus && (
                <div style={cardStyle}>
                  <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Prometheus Status</h2>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    <StatItem label="Status" value={prometheusStatus.status || 'unknown'} />
                    <StatItem label="Version" value={prometheusStatus.version || 'N/A'} />
                    <StatItem label="Uptime" value={prometheusStatus.uptime || 'N/A'} />
                    <StatItem label="Storage" value={prometheusStatus.storage || 'N/A'} />
                  </div>
                </div>
              )}

              {/* Query Interface */}
              <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
                <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Query Interface</h2>
                <form onSubmit={executePrometheusQuery} style={{ display: 'grid', gap: '1rem' }}>
                  <input
                    type="text"
                    placeholder="PromQL query (e.g., up, rate(http_requests_total[5m]))"
                    value={prometheusQuery}
                    onChange={(e) => setPrometheusQuery(e.target.value)}
                    style={inputStyle}
                    required
                  />
                  <button type="submit" style={buttonStyle}>Execute Query</button>
                </form>
                {prometheusResult && (
                  <pre style={{ backgroundColor: '#222', color: '#ddd', padding: '1rem', borderRadius: '4px', overflow: 'auto', maxHeight: '400px', marginTop: '1rem' }}>
                    {JSON.stringify(prometheusResult, null, 2)}
                  </pre>
                )}
              </div>

              {/* Targets */}
              <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
                <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Targets ({prometheusTargets.length})</h2>
                <div style={{ display: 'grid', gap: '1rem' }}>
                  {prometheusTargets.map((target, idx) => (
                    <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <h3 style={{ color: '#d4af37' }}>{target.job || 'unknown'}</h3>
                          <p style={{ color: '#999', fontSize: '0.9rem' }}>{target.instance || 'N/A'}</p>
                        </div>
                        <span style={{
                          padding: '0.25rem 0.75rem',
                          borderRadius: '4px',
                          backgroundColor: target.health === 'up' ? '#2a4a2a' : '#4a2a2a',
                          color: target.health === 'up' ? '#6fdc6f' : '#ff6b6b',
                          fontSize: '0.85rem',
                        }}>
                          {target.health || 'unknown'}
                        </span>
                      </div>
                      {target.lastScrape && (
                        <p style={{ color: '#666', fontSize: '0.85rem', marginTop: '0.5rem' }}>
                          Last scrape: {target.lastScrape}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Elasticsearch Tab */}
          {activeTab === 'elasticsearch' && (
            <div>
              {/* Status */}
              {elasticsearchStatus && (
                <div style={cardStyle}>
                  <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Elasticsearch Status</h2>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    <StatItem label="Cluster Health" value={elasticsearchStatus.cluster_health || 'unknown'} />
                    <StatItem label="Nodes" value={elasticsearchStatus.nodes || 0} />
                    <StatItem label="Indices" value={elasticsearchStatus.indices || 0} />
                    <StatItem label="Documents" value={elasticsearchStatus.documents || 0} />
                  </div>
                </div>
              )}

              {/* Search Interface */}
              <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
                <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Search Interface</h2>
                <form onSubmit={executeElasticsearchQuery} style={{ display: 'grid', gap: '1rem' }}>
                  <textarea
                    placeholder='Query DSL (e.g., {"query": {"match_all": {}}})'
                    value={elasticsearchQuery}
                    onChange={(e) => setElasticsearchQuery(e.target.value)}
                    style={{ ...inputStyle, minHeight: '100px' }}
                    required
                  />
                  <button type="submit" style={buttonStyle}>Execute Search</button>
                </form>
                {elasticsearchResult && (
                  <pre style={{ backgroundColor: '#222', color: '#ddd', padding: '1rem', borderRadius: '4px', overflow: 'auto', maxHeight: '400px', marginTop: '1rem' }}>
                    {JSON.stringify(elasticsearchResult, null, 2)}
                  </pre>
                )}
              </div>

              {/* Indices */}
              <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
                <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Indices ({elasticsearchIndices.length})</h2>
                <div style={{ display: 'grid', gap: '1rem' }}>
                  {elasticsearchIndices.map((index, idx) => (
                    <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px' }}>
                      <h3 style={{ color: '#d4af37' }}>{index.name}</h3>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <p style={{ color: '#999', fontSize: '0.85rem' }}>Docs: {index.docs || 0}</p>
                        <p style={{ color: '#999', fontSize: '0.85rem' }}>Size: {index.size || 'N/A'}</p>
                        <p style={{ color: '#999', fontSize: '0.85rem' }}>Shards: {index.shards || 0}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Grafana Tab */}
          {activeTab === 'grafana' && (
            <div>
              {/* Status */}
              {grafanaStatus && (
                <div style={cardStyle}>
                  <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Grafana Status</h2>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    <StatItem label="Status" value={grafanaStatus.status || 'unknown'} />
                    <StatItem label="Version" value={grafanaStatus.version || 'N/A'} />
                    <StatItem label="Dashboards" value={grafanaStatus.dashboards || 0} />
                    <StatItem label="Users" value={grafanaStatus.users || 0} />
                  </div>
                </div>
              )}

              {/* Dashboards */}
              <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
                <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Dashboards ({grafanaDashboards.length})</h2>
                <div style={{ display: 'grid', gap: '1rem' }}>
                  {grafanaDashboards.map((dashboard, idx) => (
                    <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <h3 style={{ color: '#d4af37' }}>{dashboard.title}</h3>
                        <p style={{ color: '#999', fontSize: '0.9rem' }}>{dashboard.folder || 'General'}</p>
                        {dashboard.tags && (
                          <p style={{ color: '#666', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                            Tags: {dashboard.tags.join(', ')}
                          </p>
                        )}
                      </div>
                      <a
                        href={dashboard.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ ...buttonStyle, textDecoration: 'none', display: 'inline-block' }}
                      >
                        Open
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* AlertManager Tab */}
          {activeTab === 'alertmanager' && (
            <div>
              {/* Status */}
              {alertmanagerStatus && (
                <div style={cardStyle}>
                  <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>AlertManager Status</h2>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    <StatItem label="Status" value={alertmanagerStatus.status || 'unknown'} />
                    <StatItem label="Version" value={alertmanagerStatus.version || 'N/A'} />
                    <StatItem label="Active Alerts" value={alertmanagerStatus.active_alerts || 0} />
                    <StatItem label="Silences" value={alertmanagerStatus.silences || 0} />
                  </div>
                </div>
              )}

              {/* Active Alerts */}
              <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
                <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Active Alerts ({alerts.length})</h2>
                <div style={{ display: 'grid', gap: '1rem' }}>
                  {alerts.map((alert, idx) => (
                    <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <h3 style={{ color: '#d4af37' }}>{alert.name}</h3>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <span style={{
                            padding: '0.25rem 0.75rem',
                            borderRadius: '4px',
                            backgroundColor: alert.severity === 'critical' ? '#4a2a2a' : alert.severity === 'warning' ? '#4a4a2a' : '#2a2a4a',
                            color: alert.severity === 'critical' ? '#ff6b6b' : alert.severity === 'warning' ? '#ffd93d' : '#6b9fff',
                            fontSize: '0.85rem',
                          }}>
                            {alert.severity || 'info'}
                          </span>
                          <button onClick={() => silenceAlert(alert.id)} style={{ ...buttonStyle, padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}>
                            Silence
                          </button>
                        </div>
                      </div>
                      <p style={{ color: '#999', fontSize: '0.9rem', marginBottom: '0.5rem' }}>{alert.description}</p>
                      {alert.labels && (
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                          {Object.entries(alert.labels).map(([key, value]) => (
                            <span key={key} style={{ backgroundColor: '#1a1a1a', color: '#666', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                              {key}: {value}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Silences */}
              <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
                <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Active Silences ({silences.length})</h2>
                <div style={{ display: 'grid', gap: '1rem' }}>
                  {silences.map((silence, idx) => (
                    <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px' }}>
                      <h3 style={{ color: '#d4af37' }}>{silence.comment || 'No comment'}</h3>
                      <p style={{ color: '#999', fontSize: '0.9rem' }}>
                        Created by: {silence.createdBy} | Expires: {silence.endsAt}
                      </p>
                      {silence.matchers && (
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                          {silence.matchers.map((matcher, mIdx) => (
                            <span key={mIdx} style={{ backgroundColor: '#1a1a1a', color: '#666', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                              {matcher.name}={matcher.value}
                            </span>
                          ))}
                        </div>
                      )}
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

const StatItem = ({ label, value }) => (
  <div>
    <p style={{ color: '#999', fontSize: '0.85rem', marginBottom: '0.25rem' }}>{label}</p>
    <p style={{ color: '#d4af37', fontSize: '1.1rem', fontWeight: 'bold' }}>{value}</p>
  </div>
);

const cardStyle = {
  backgroundColor: '#2a2a2a',
  border: '1px solid #d4af37',
  borderRadius: '8px',
  padding: '1.5rem',
};

const inputStyle = {
  backgroundColor: '#1a1a1a',
  border: '1px solid #444',
  borderRadius: '4px',
  padding: '0.75rem',
  color: '#ddd',
  fontSize: '1rem',
};

const buttonStyle = {
  backgroundColor: '#d4af37',
  color: '#1a1a1a',
  border: 'none',
  borderRadius: '4px',
  padding: '0.75rem 1.5rem',
  cursor: 'pointer',
  fontWeight: 'bold',
  fontSize: '1rem',
};

export default Infrastructure;

import React, { useState, useEffect } from 'react';

const Metrics = () => {
  const [query, setQuery] = useState('');
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [timeRange, setTimeRange] = useState('1h');
  const [step, setStep] = useState('15s');

  const prebuiltQueries = [
    { name: 'CPU Usage', query: 'rate(process_cpu_seconds_total[5m]) * 100', unit: '%' },
    { name: 'Memory Usage', query: 'process_resident_memory_bytes / 1024 / 1024', unit: 'MB' },
    { name: 'Network RX', query: 'rate(network_receive_bytes_total[5m])', unit: 'B/s' },
    { name: 'Network TX', query: 'rate(network_transmit_bytes_total[5m])', unit: 'B/s' },
    { name: 'Disk Usage', query: 'disk_used_percent', unit: '%' },
    { name: 'HTTP Requests', query: 'rate(http_requests_total[5m])', unit: 'req/s' },
  ];

  const [prebuiltMetrics, setPrebuiltMetrics] = useState({});

  const executeQuery = async (promqlQuery) => {
    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams({ query: promqlQuery, time: Date.now() / 1000 });
      const response = await fetch(`/api/v1/infrastructure/prometheus/query?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Failed to fetch metrics');

      return data.data?.result || [];
    } catch (err) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    const results = await executeQuery(query);
    setMetrics(results);
  };

  const loadPrebuiltMetrics = async () => {
    const results = {};
    for (const metric of prebuiltQueries) {
      const data = await executeQuery(metric.query);
      results[metric.name] = data;
    }
    setPrebuiltMetrics(results);
  };

  useEffect(() => {
    loadPrebuiltMetrics();
    const interval = setInterval(loadPrebuiltMetrics, 30000);
    return () => clearInterval(interval);
  }, [timeRange]);

  const formatValue = (value, unit) => {
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    return `${num.toFixed(2)} ${unit}`;
  };

  return (
    <div style={{ backgroundColor: '#1a1a1a', minHeight: '100vh', padding: '1.5rem' }}>
      <h1 style={{ color: '#d4af37', marginBottom: '1.5rem' }}>Metrics Viewer</h1>

      <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem', fontSize: '1.2rem' }}>PromQL Query</h2>

        <form onSubmit={handleSearch}>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <input type="text" placeholder="Enter PromQL query..." value={query} onChange={(e) => setQuery(e.target.value)} style={{ flex: '1', minWidth: '300px', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff', fontFamily: 'monospace' }} />
            <button type="submit" disabled={loading} style={{ padding: '0.75rem 1.5rem', backgroundColor: '#d4af37', color: '#1a1a1a', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: loading ? 'not-allowed' : 'pointer' }}>
              Execute
            </button>
          </div>

          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <label style={{ color: '#999', fontSize: '0.9rem', marginRight: '0.5rem' }}>Time Range:</label>
              <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)} style={{ padding: '0.5rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }}>
                <option value="5m">Last 5 minutes</option>
                <option value="15m">Last 15 minutes</option>
                <option value="1h">Last 1 hour</option>
                <option value="6h">Last 6 hours</option>
                <option value="24h">Last 24 hours</option>
              </select>
            </div>

            <div>
              <label style={{ color: '#999', fontSize: '0.9rem', marginRight: '0.5rem' }}>Step:</label>
              <select value={step} onChange={(e) => setStep(e.target.value)} style={{ padding: '0.5rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }}>
                <option value="15s">15 seconds</option>
                <option value="30s">30 seconds</option>
                <option value="1m">1 minute</option>
                <option value="5m">5 minutes</option>
              </select>
            </div>
          </div>
        </form>

        {error && <div style={{ backgroundColor: '#3a1a1a', border: '1px solid #ff4444', borderRadius: '4px', padding: '1rem', marginTop: '1rem', color: '#ff6666' }}>{error}</div>}

        {metrics.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <h3 style={{ color: '#d4af37', marginBottom: '0.5rem' }}>Results:</h3>
            <pre style={{ backgroundColor: '#1a1a1a', padding: '1rem', borderRadius: '4px', color: '#fff', fontSize: '0.85rem', overflow: 'auto', maxHeight: '300px' }}>{JSON.stringify(metrics, null, 2)}</pre>
          </div>
        )}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem', fontSize: '1.2rem' }}>System Metrics</h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
          {prebuiltQueries.map((metric) => {
            const data = prebuiltMetrics[metric.name] || [];
            const value = data[0]?.value?.[1] || '0';

            return (
              <div key={metric.name} onClick={() => setQuery(metric.query)} style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '1.5rem', cursor: 'pointer', transition: 'transform 0.2s, box-shadow 0.2s' }} onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(212, 175, 55, 0.2)'; }} onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}>
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ color: '#999', fontSize: '0.9rem' }}>{metric.name}</span>
                </div>
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ color: '#d4af37', fontSize: '2rem', fontWeight: 'bold' }}>{formatValue(value, metric.unit)}</span>
                </div>
                <div>
                  <code style={{ color: '#666', fontSize: '0.75rem', backgroundColor: '#1a1a1a', padding: '0.25rem 0.5rem', borderRadius: '3px', display: 'inline-block' }}>{metric.query}</code>
                </div>

                {data.length > 0 && (
                  <div style={{ marginTop: '1rem' }}>
                    <div style={{ height: '60px', backgroundColor: '#1a1a1a', borderRadius: '4px', position: 'relative', overflow: 'hidden' }}>
                      {data.slice(0, 20).map((point, idx) => {
                        const val = parseFloat(point.value[1]);
                        const maxVal = Math.max(...data.slice(0, 20).map(p => parseFloat(p.value[1])));
                        const height = maxVal > 0 ? (val / maxVal) * 100 : 0;

                        return <div key={idx} style={{ position: 'absolute', bottom: 0, left: `${(idx / 20) * 100}%`, width: '5%', height: `${height}%`, backgroundColor: '#d4af37', opacity: 0.7 }} />;
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '1.5rem' }}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem', fontSize: '1.2rem' }}>Query Examples</h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmin(300px, 1fr))', gap: '1rem' }}>
          {[
            { desc: 'Rate of requests', query: 'rate(http_requests_total[5m])' },
            { desc: 'Average response time', query: 'avg(http_request_duration_seconds)' },
            { desc: 'Error rate', query: 'rate(http_requests_total{status=~"5.."}[5m])' },
            { desc: 'Memory by service', query: 'sum by (service) (process_resident_memory_bytes)' },
          ].map((example, idx) => (
            <div key={idx} onClick={() => setQuery(example.query)} style={{ padding: '1rem', backgroundColor: '#1a1a1a', borderRadius: '4px', cursor: 'pointer', border: '1px solid transparent', transition: 'border-color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.borderColor = '#d4af37'} onMouseLeave={(e) => e.currentTarget.style.borderColor = 'transparent'}>
              <div style={{ color: '#999', fontSize: '0.9rem', marginBottom: '0.5rem' }}>{example.desc}</div>
              <code style={{ color: '#d4af37', fontSize: '0.85rem' }}>{example.query}</code>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Metrics;

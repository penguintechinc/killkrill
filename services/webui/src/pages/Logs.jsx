import React, { useState, useEffect } from 'react';

const Logs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [logLevel, setLogLevel] = useState('all');
  const [source, setSource] = useState('');
  const [timeRange, setTimeRange] = useState('1h');
  const [selectedLog, setSelectedLog] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchLogs = async () => {
    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams({
        query: searchQuery || '*',
        size: '100',
        from: '0',
      });

      if (logLevel !== 'all') params.append('level', logLevel);
      if (source) params.append('source', source);
      if (timeRange) params.append('time_range', timeRange);

      const response = await fetch(`/api/v1/infrastructure/elasticsearch/search?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Failed to fetch logs');

      setLogs(data.hits?.hits || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLogs(); }, [logLevel, source, timeRange]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchLogs, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, searchQuery, logLevel, source, timeRange]);

  const handleSearch = (e) => { e.preventDefault(); fetchLogs(); };

  const getLevelColor = (level) => {
    const colors = { error: '#ff4444', warn: '#ffaa00', info: '#4488ff', debug: '#888' };
    return colors[level?.toLowerCase()] || '#999';
  };

  return (
    <div style={{ backgroundColor: '#1a1a1a', minHeight: '100vh', padding: '1.5rem' }}>
      <h1 style={{ color: '#d4af37', marginBottom: '1.5rem' }}>Log Viewer</h1>

      <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <form onSubmit={handleSearch} style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              type="text"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: '1', minWidth: '250px', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }}
            />
            <button type="submit" disabled={loading} style={{ padding: '0.75rem 1.5rem', backgroundColor: '#d4af37', color: '#1a1a1a', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: loading ? 'not-allowed' : 'pointer' }}>
              Search
            </button>
          </div>
        </form>

        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <label style={{ color: '#999', fontSize: '0.9rem', marginRight: '0.5rem' }}>Level:</label>
            <select value={logLevel} onChange={(e) => setLogLevel(e.target.value)} style={{ padding: '0.5rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }}>
              <option value="all">All</option>
              <option value="error">Error</option>
              <option value="warn">Warning</option>
              <option value="info">Info</option>
              <option value="debug">Debug</option>
            </select>
          </div>

          <div>
            <label style={{ color: '#999', fontSize: '0.9rem', marginRight: '0.5rem' }}>Time Range:</label>
            <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)} style={{ padding: '0.5rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }}>
              <option value="15m">Last 15 minutes</option>
              <option value="1h">Last 1 hour</option>
              <option value="6h">Last 6 hours</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
            </select>
          </div>

          <div>
            <label style={{ color: '#999', fontSize: '0.9rem', marginRight: '0.5rem' }}>Source:</label>
            <input type="text" placeholder="Filter by source..." value={source} onChange={(e) => setSource(e.target.value)} style={{ padding: '0.5rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff', width: '180px' }} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input type="checkbox" id="autoRefresh" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} style={{ cursor: 'pointer' }} />
            <label htmlFor="autoRefresh" style={{ color: '#999', fontSize: '0.9rem', cursor: 'pointer' }}>Auto-refresh (5s)</label>
          </div>
        </div>
      </div>

      {error && <div style={{ backgroundColor: '#3a1a1a', border: '1px solid #ff4444', borderRadius: '4px', padding: '1rem', marginBottom: '1rem', color: '#ff6666' }}>{error}</div>}

      <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', overflow: 'hidden' }}>
        <div style={{ padding: '1rem', borderBottom: '1px solid #444' }}>
          <span style={{ color: '#999' }}>{loading ? 'Loading...' : `${logs.length} logs`}</span>
        </div>

        <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
          {logs.map((log, idx) => {
            const src = log._source || {};
            const level = src.level || 'info';
            return (
              <div key={log._id || idx} onClick={() => setSelectedLog(log)} style={{ padding: '1rem', borderBottom: '1px solid #333', cursor: 'pointer', transition: 'background-color 0.2s', backgroundColor: selectedLog?._id === log._id ? '#3a3a3a' : 'transparent' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#3a3a3a'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = selectedLog?._id === log._id ? '#3a3a3a' : 'transparent'}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                  <span style={{ color: getLevelColor(level), fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.8rem', minWidth: '60px' }}>{level}</span>
                  <span style={{ color: '#666', fontSize: '0.85rem', minWidth: '150px' }}>{src.timestamp || src['@timestamp'] || 'No timestamp'}</span>
                  <span style={{ color: '#999', fontSize: '0.85rem', minWidth: '120px' }}>{src.source || src.hostname || 'Unknown'}</span>
                  <span style={{ color: '#fff', flex: '1' }}>{src.message || JSON.stringify(src).substring(0, 100)}</span>
                </div>
              </div>
            );
          })}
          {logs.length === 0 && !loading && <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>No logs found</div>}
        </div>
      </div>

      {selectedLog && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0, 0, 0, 0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={() => setSelectedLog(null)}>
          <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '2rem', maxWidth: '800px', maxHeight: '80vh', overflowY: 'auto', width: '90%' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ color: '#d4af37' }}>Log Details</h2>
              <button onClick={() => setSelectedLog(null)} style={{ backgroundColor: 'transparent', border: 'none', color: '#999', fontSize: '1.5rem', cursor: 'pointer' }}>×</button>
            </div>
            <pre style={{ backgroundColor: '#1a1a1a', padding: '1rem', borderRadius: '4px', color: '#fff', fontSize: '0.9rem', overflow: 'auto' }}>{JSON.stringify(selectedLog, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default Logs;

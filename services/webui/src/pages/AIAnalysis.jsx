import React, { useState, useEffect } from 'react';

const AIAnalysis = () => {
  const [analysisType, setAnalysisType] = useState('anomaly');
  const [dataInput, setDataInput] = useState('');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [insights, setInsights] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [recentAnalyses, setRecentAnalyses] = useState([]);

  const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8080/api/v1';

  useEffect(() => {
    fetchRecentAnalyses();
    fetchInsights();
    fetchAnomalies();
    fetchRecommendations();
  }, []);

  const fetchRecentAnalyses = async () => {
    try {
      const res = await fetch(`${API_BASE}/ai/analyses`);
      const data = await res.json();
      setRecentAnalyses(data.analyses || []);
    } catch (err) {
      console.error('Failed to fetch recent analyses:', err);
    }
  };

  const fetchInsights = async () => {
    try {
      const res = await fetch(`${API_BASE}/ai/insights`);
      const data = await res.json();
      setInsights(data.insights || []);
    } catch (err) {
      console.error('Failed to fetch insights:', err);
    }
  };

  const fetchAnomalies = async () => {
    try {
      const res = await fetch(`${API_BASE}/ai/anomalies`);
      const data = await res.json();
      setAnomalies(data.anomalies || []);
    } catch (err) {
      console.error('Failed to fetch anomalies:', err);
    }
  };

  const fetchRecommendations = async () => {
    try {
      const res = await fetch(`${API_BASE}/ai/recommendations`);
      const data = await res.json();
      setRecommendations(data.recommendations || []);
    } catch (err) {
      console.error('Failed to fetch recommendations:', err);
    }
  };

  const submitAnalysis = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setAnalysisResult(null);

    try {
      const res = await fetch(`${API_BASE}/ai/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: analysisType,
          data: dataInput,
          timestamp: new Date().toISOString(),
        }),
      });

      if (!res.ok) {
        throw new Error(`Analysis failed: ${res.statusText}`);
      }

      const data = await res.json();
      setAnalysisResult(data);

      // Refresh all data after analysis
      fetchRecentAnalyses();
      fetchInsights();
      fetchAnomalies();
      fetchRecommendations();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const analysisTypes = [
    { id: 'anomaly', label: 'Anomaly Detection', description: 'Detect unusual patterns in logs and metrics' },
    { id: 'prediction', label: 'Predictive Analysis', description: 'Forecast trends and potential issues' },
    { id: 'classification', label: 'Log Classification', description: 'Categorize and classify log entries' },
    { id: 'correlation', label: 'Event Correlation', description: 'Find relationships between events' },
    { id: 'optimization', label: 'Performance Optimization', description: 'Identify optimization opportunities' },
  ];

  return (
    <div className="p-6" style={{ backgroundColor: '#1a1a1a', minHeight: '100vh' }}>
      <h1 style={{ color: '#d4af37', marginBottom: '2rem' }}>AI Analysis</h1>

      {/* Analysis Submission Form */}
      <div style={cardStyle}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Submit Data for Analysis</h2>
        <form onSubmit={submitAnalysis} style={{ display: 'grid', gap: '1rem' }}>
          <div>
            <label style={{ color: '#999', fontSize: '0.9rem', display: 'block', marginBottom: '0.5rem' }}>
              Analysis Type
            </label>
            <select
              value={analysisType}
              onChange={(e) => setAnalysisType(e.target.value)}
              style={inputStyle}
            >
              {analysisTypes.map(type => (
                <option key={type.id} value={type.id}>
                  {type.label} - {type.description}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ color: '#999', fontSize: '0.9rem', display: 'block', marginBottom: '0.5rem' }}>
              Data Input (JSON, CSV, or plain text)
            </label>
            <textarea
              value={dataInput}
              onChange={(e) => setDataInput(e.target.value)}
              placeholder='Enter data to analyze (e.g., {"timestamp": "2024-01-01", "value": 42})'
              style={{ ...inputStyle, minHeight: '150px', fontFamily: 'monospace' }}
              required
            />
          </div>

          <button type="submit" style={buttonStyle} disabled={loading}>
            {loading ? 'Analyzing...' : 'Run Analysis'}
          </button>
        </form>

        {error && (
          <div style={{ backgroundColor: '#3a1a1a', color: '#ff6b6b', padding: '1rem', borderRadius: '4px', marginTop: '1rem' }}>
            Error: {error}
          </div>
        )}

        {analysisResult && (
          <div style={{ marginTop: '1.5rem' }}>
            <h3 style={{ color: '#d4af37', marginBottom: '1rem' }}>Analysis Results</h3>
            <div style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px' }}>
              <div style={{ marginBottom: '1rem' }}>
                <p style={{ color: '#999', fontSize: '0.85rem' }}>Analysis ID: {analysisResult.id}</p>
                <p style={{ color: '#999', fontSize: '0.85rem' }}>Type: {analysisResult.type}</p>
                <p style={{ color: '#999', fontSize: '0.85rem' }}>Timestamp: {analysisResult.timestamp}</p>
              </div>
              <pre style={{
                backgroundColor: '#1a1a1a',
                color: '#ddd',
                padding: '1rem',
                borderRadius: '4px',
                overflow: 'auto',
                maxHeight: '400px',
                fontSize: '0.85rem',
              }}>
                {JSON.stringify(analysisResult, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* AI Insights */}
      <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>AI Insights ({insights.length})</h2>
        <div style={{ display: 'grid', gap: '1rem' }}>
          {insights.length === 0 ? (
            <p style={{ color: '#999' }}>No insights available yet. Submit data for analysis to generate insights.</p>
          ) : (
            insights.map((insight, idx) => (
              <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h3 style={{ color: '#d4af37' }}>{insight.title}</h3>
                  <span style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '4px',
                    backgroundColor: insight.priority === 'high' ? '#4a2a2a' : insight.priority === 'medium' ? '#4a4a2a' : '#2a2a4a',
                    color: insight.priority === 'high' ? '#ff6b6b' : insight.priority === 'medium' ? '#ffd93d' : '#6b9fff',
                    fontSize: '0.85rem',
                  }}>
                    {insight.priority || 'info'}
                  </span>
                </div>
                <p style={{ color: '#ddd', fontSize: '0.95rem', marginBottom: '0.5rem' }}>{insight.description}</p>
                <p style={{ color: '#666', fontSize: '0.85rem' }}>Generated: {insight.timestamp}</p>
                {insight.confidence && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <p style={{ color: '#999', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                      Confidence: {Math.round(insight.confidence * 100)}%
                    </p>
                    <div style={{ backgroundColor: '#1a1a1a', height: '8px', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{
                        backgroundColor: '#d4af37',
                        height: '100%',
                        width: `${insight.confidence * 100}%`,
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Anomaly Detection Results */}
      <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Detected Anomalies ({anomalies.length})</h2>
        <div style={{ display: 'grid', gap: '1rem' }}>
          {anomalies.length === 0 ? (
            <p style={{ color: '#999' }}>No anomalies detected. System is operating normally.</p>
          ) : (
            anomalies.map((anomaly, idx) => (
              <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px', border: '1px solid #aa3333' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h3 style={{ color: '#ff6b6b' }}>{anomaly.type || 'Anomaly'}</h3>
                  <span style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '4px',
                    backgroundColor: '#4a2a2a',
                    color: '#ff6b6b',
                    fontSize: '0.85rem',
                  }}>
                    Severity: {anomaly.severity || 'unknown'}
                  </span>
                </div>
                <p style={{ color: '#ddd', fontSize: '0.95rem', marginBottom: '0.5rem' }}>{anomaly.description}</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.5rem' }}>
                  <p style={{ color: '#999', fontSize: '0.85rem' }}>Detected: {anomaly.timestamp}</p>
                  <p style={{ color: '#999', fontSize: '0.85rem' }}>Source: {anomaly.source || 'N/A'}</p>
                </div>
                {anomaly.score && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <p style={{ color: '#999', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                      Anomaly Score: {anomaly.score.toFixed(2)}
                    </p>
                    <div style={{ backgroundColor: '#1a1a1a', height: '8px', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{
                        backgroundColor: '#ff6b6b',
                        height: '100%',
                        width: `${Math.min(anomaly.score * 10, 100)}%`,
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Recommendations */}
      <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>AI Recommendations ({recommendations.length})</h2>
        <div style={{ display: 'grid', gap: '1rem' }}>
          {recommendations.length === 0 ? (
            <p style={{ color: '#999' }}>No recommendations available. Submit data for analysis to receive recommendations.</p>
          ) : (
            recommendations.map((rec, idx) => (
              <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px', border: '1px solid #d4af37' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h3 style={{ color: '#d4af37' }}>{rec.title}</h3>
                  <span style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '4px',
                    backgroundColor: rec.impact === 'high' ? '#2a4a2a' : rec.impact === 'medium' ? '#4a4a2a' : '#2a2a4a',
                    color: rec.impact === 'high' ? '#6fdc6f' : rec.impact === 'medium' ? '#ffd93d' : '#6b9fff',
                    fontSize: '0.85rem',
                  }}>
                    Impact: {rec.impact || 'low'}
                  </span>
                </div>
                <p style={{ color: '#ddd', fontSize: '0.95rem', marginBottom: '0.5rem' }}>{rec.description}</p>
                {rec.actions && rec.actions.length > 0 && (
                  <div style={{ marginTop: '0.75rem' }}>
                    <p style={{ color: '#999', fontSize: '0.85rem', marginBottom: '0.5rem' }}>Suggested Actions:</p>
                    <ul style={{ color: '#ddd', fontSize: '0.9rem', marginLeft: '1.5rem' }}>
                      {rec.actions.map((action, aIdx) => (
                        <li key={aIdx} style={{ marginBottom: '0.25rem' }}>{action}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <p style={{ color: '#666', fontSize: '0.85rem', marginTop: '0.5rem' }}>
                  Generated: {rec.timestamp}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Recent Analyses */}
      <div style={{ ...cardStyle, marginTop: '1.5rem' }}>
        <h2 style={{ color: '#d4af37', marginBottom: '1rem' }}>Recent Analyses ({recentAnalyses.length})</h2>
        <div style={{ display: 'grid', gap: '1rem' }}>
          {recentAnalyses.length === 0 ? (
            <p style={{ color: '#999' }}>No recent analyses. Submit data above to get started.</p>
          ) : (
            recentAnalyses.slice(0, 10).map((analysis, idx) => (
              <div key={idx} style={{ backgroundColor: '#222', padding: '1rem', borderRadius: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ color: '#d4af37' }}>{analysis.type} Analysis</h3>
                    <p style={{ color: '#999', fontSize: '0.85rem' }}>ID: {analysis.id}</p>
                    <p style={{ color: '#999', fontSize: '0.85rem' }}>Completed: {analysis.timestamp}</p>
                  </div>
                  <span style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '4px',
                    backgroundColor: analysis.status === 'completed' ? '#2a4a2a' : analysis.status === 'failed' ? '#4a2a2a' : '#4a4a2a',
                    color: analysis.status === 'completed' ? '#6fdc6f' : analysis.status === 'failed' ? '#ff6b6b' : '#ffd93d',
                    fontSize: '0.85rem',
                  }}>
                    {analysis.status || 'unknown'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

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
  width: '100%',
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

export default AIAnalysis;

import React, { useState, useEffect } from 'react';

const Settings = () => {
  const [activeTab, setActiveTab] = useState('users');

  const tabs = [
    { id: 'users', label: 'Users' },
    { id: 'apikeys', label: 'API Keys' },
    { id: 'license', label: 'License' },
    { id: 'system', label: 'System' },
  ];

  return (
    <div style={{ backgroundColor: '#1a1a1a', minHeight: '100vh', padding: '1.5rem' }}>
      <h1 style={{ color: '#d4af37', marginBottom: '1.5rem' }}>Settings</h1>

      <div style={{ marginBottom: '1.5rem', borderBottom: '1px solid #444' }}>
        <div style={{ display: 'flex', gap: '1rem' }}>
          {tabs.map((tab) => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{ padding: '1rem 1.5rem', backgroundColor: 'transparent', border: 'none', borderBottom: activeTab === tab.id ? '2px solid #d4af37' : '2px solid transparent', color: activeTab === tab.id ? '#d4af37' : '#999', fontWeight: activeTab === tab.id ? 'bold' : 'normal', cursor: 'pointer', transition: 'all 0.2s' }}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'users' && <UsersTab />}
      {activeTab === 'apikeys' && <ApiKeysTab />}
      {activeTab === 'license' && <LicenseTab />}
      {activeTab === 'system' && <SystemTab />}
    </div>
  );
};

const UsersTab = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({ username: '', email: '', password: '', role: 'user' });

  const fetchUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/users', { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Failed to fetch users');
      setUsers(data.users || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const url = editingUser ? `/api/v1/users/${editingUser.id}` : '/api/v1/users';
      const method = editingUser ? 'PUT' : 'POST';
      const response = await fetch(url, { method, headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Operation failed');
      setShowForm(false);
      setEditingUser(null);
      setFormData({ username: '', email: '', password: '', role: 'user' });
      fetchUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (userId) => {
    if (!confirm('Are you sure?')) return;
    try {
      const response = await fetch(`/api/v1/users/${userId}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      if (!response.ok) throw new Error('Delete failed');
      fetchUsers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({ username: user.username, email: user.email, password: '', role: user.role });
    setShowForm(true);
  };

  return (
    <div>
      {error && <div style={{ backgroundColor: '#3a1a1a', border: '1px solid #ff4444', borderRadius: '4px', padding: '1rem', marginBottom: '1rem', color: '#ff6666' }}>{error}</div>}

      <button onClick={() => { setShowForm(!showForm); setEditingUser(null); setFormData({ username: '', email: '', password: '', role: 'user' }); }} style={{ padding: '0.75rem 1.5rem', backgroundColor: '#d4af37', color: '#1a1a1a', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', marginBottom: '1.5rem' }}>
        {showForm ? 'Cancel' : 'Add User'}
      </button>

      {showForm && (
        <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '1.5rem', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#d4af37', marginBottom: '1rem' }}>{editingUser ? 'Edit User' : 'Create User'}</h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', color: '#999', marginBottom: '0.5rem' }}>Username</label>
                <input type="text" value={formData.username} onChange={(e) => setFormData({ ...formData, username: e.target.value })} required style={{ width: '100%', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }} />
              </div>
              <div>
                <label style={{ display: 'block', color: '#999', marginBottom: '0.5rem' }}>Email</label>
                <input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} required style={{ width: '100%', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }} />
              </div>
              <div>
                <label style={{ display: 'block', color: '#999', marginBottom: '0.5rem' }}>Password {editingUser && '(leave blank to keep)'}</label>
                <input type="password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} required={!editingUser} style={{ width: '100%', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }} />
              </div>
              <div>
                <label style={{ display: 'block', color: '#999', marginBottom: '0.5rem' }}>Role</label>
                <select value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })} style={{ width: '100%', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }}>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            <button type="submit" style={{ padding: '0.75rem 1.5rem', backgroundColor: '#d4af37', color: '#1a1a1a', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}>
              {editingUser ? 'Update' : 'Create'}
            </button>
          </form>
        </div>
      )}

      <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#333' }}>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Username</th>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Email</th>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Role</th>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} style={{ borderTop: '1px solid #333' }}>
                <td style={{ padding: '1rem', color: '#fff' }}>{user.username}</td>
                <td style={{ padding: '1rem', color: '#999' }}>{user.email}</td>
                <td style={{ padding: '1rem', color: '#999' }}>{user.role}</td>
                <td style={{ padding: '1rem' }}>
                  <button onClick={() => handleEdit(user)} style={{ padding: '0.5rem 1rem', backgroundColor: 'transparent', border: '1px solid #d4af37', borderRadius: '4px', color: '#d4af37', cursor: 'pointer', marginRight: '0.5rem' }}>Edit</button>
                  <button onClick={() => handleDelete(user.id)} style={{ padding: '0.5rem 1rem', backgroundColor: 'transparent', border: '1px solid #ff4444', borderRadius: '4px', color: '#ff4444', cursor: 'pointer' }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && !loading && <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>No users found</div>}
      </div>
    </div>
  );
};

const ApiKeysTab = () => {
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ name: '', expires_in_days: 365 });

  const fetchApiKeys = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/auth/api-keys', { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Failed to fetch API keys');
      setApiKeys(data.api_keys || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchApiKeys(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const response = await fetch('/api/v1/auth/api-keys', { method: 'POST', headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Operation failed');
      setShowForm(false);
      setFormData({ name: '', expires_in_days: 365 });
      fetchApiKeys();
      alert(`API Key: ${data.api_key}\n\nSave this - it won't be shown again!`);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (keyId) => {
    if (!confirm('Revoke this key?')) return;
    try {
      const response = await fetch(`/api/v1/auth/api-keys/${keyId}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      if (!response.ok) throw new Error('Delete failed');
      fetchApiKeys();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      {error && <div style={{ backgroundColor: '#3a1a1a', border: '1px solid #ff4444', borderRadius: '4px', padding: '1rem', marginBottom: '1rem', color: '#ff6666' }}>{error}</div>}

      <button onClick={() => { setShowForm(!showForm); setFormData({ name: '', expires_in_days: 365 }); }} style={{ padding: '0.75rem 1.5rem', backgroundColor: '#d4af37', color: '#1a1a1a', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', marginBottom: '1.5rem' }}>
        {showForm ? 'Cancel' : 'Create API Key'}
      </button>

      {showForm && (
        <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '1.5rem', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#d4af37', marginBottom: '1rem' }}>Create API Key</h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', color: '#999', marginBottom: '0.5rem' }}>Key Name</label>
                <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required placeholder="Production API Key" style={{ width: '100%', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }} />
              </div>
              <div>
                <label style={{ display: 'block', color: '#999', marginBottom: '0.5rem' }}>Expires In (days)</label>
                <input type="number" value={formData.expires_in_days} onChange={(e) => setFormData({ ...formData, expires_in_days: parseInt(e.target.value) })} required min="1" max="3650" style={{ width: '100%', padding: '0.75rem', backgroundColor: '#1a1a1a', border: '1px solid #444', borderRadius: '4px', color: '#fff' }} />
              </div>
            </div>
            <button type="submit" style={{ padding: '0.75rem 1.5rem', backgroundColor: '#d4af37', color: '#1a1a1a', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}>Create Key</button>
          </form>
        </div>
      )}

      <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#333' }}>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Name</th>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Key (partial)</th>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Created</th>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Expires</th>
              <th style={{ padding: '1rem', textAlign: 'left', color: '#d4af37' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {apiKeys.map((key) => (
              <tr key={key.id} style={{ borderTop: '1px solid #333' }}>
                <td style={{ padding: '1rem', color: '#fff' }}>{key.name}</td>
                <td style={{ padding: '1rem', color: '#999', fontFamily: 'monospace' }}>{key.key_preview || '****...****'}</td>
                <td style={{ padding: '1rem', color: '#999' }}>{new Date(key.created_at).toLocaleDateString()}</td>
                <td style={{ padding: '1rem', color: '#999' }}>{new Date(key.expires_at).toLocaleDateString()}</td>
                <td style={{ padding: '1rem' }}>
                  <button onClick={() => handleDelete(key.id)} style={{ padding: '0.5rem 1rem', backgroundColor: 'transparent', border: '1px solid #ff4444', borderRadius: '4px', color: '#ff4444', cursor: 'pointer' }}>Revoke</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {apiKeys.length === 0 && !loading && <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>No API keys found</div>}
      </div>
    </div>
  );
};

const LicenseTab = () => {
  const [license, setLicense] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [validating, setValidating] = useState(false);

  const fetchLicense = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/licensing/info', { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Failed to fetch license');
      setLicense(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const validateLicense = async () => {
    setValidating(true);
    setError('');
    try {
      const response = await fetch('/api/v1/licensing/validate', { method: 'POST', headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Validation failed');
      alert('License validated successfully!');
      fetchLicense();
    } catch (err) {
      setError(err.message);
    } finally {
      setValidating(false);
    }
  };

  useEffect(() => { fetchLicense(); }, []);

  const getTierColor = (tier) => {
    const colors = { community: '#4488ff', professional: '#d4af37', enterprise: '#ff8800' };
    return colors[tier?.toLowerCase()] || '#999';
  };

  return (
    <div>
      {error && <div style={{ backgroundColor: '#3a1a1a', border: '1px solid #ff4444', borderRadius: '4px', padding: '1rem', marginBottom: '1rem', color: '#ff6666' }}>{error}</div>}

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#999' }}>Loading...</div>
      ) : license ? (
        <div>
          <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '2rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '2rem' }}>
              <div>
                <h3 style={{ color: '#999', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Customer</h3>
                <p style={{ color: '#fff', fontSize: '1.2rem' }}>{license.customer}</p>
              </div>
              <div>
                <h3 style={{ color: '#999', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Tier</h3>
                <p style={{ color: getTierColor(license.tier), fontSize: '1.2rem', textTransform: 'uppercase', fontWeight: 'bold' }}>{license.tier}</p>
              </div>
              <div>
                <h3 style={{ color: '#999', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Key</h3>
                <p style={{ color: '#fff', fontSize: '1rem', fontFamily: 'monospace' }}>{license.license_key}</p>
              </div>
              <div>
                <h3 style={{ color: '#999', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Expires</h3>
                <p style={{ color: '#fff', fontSize: '1.2rem' }}>{new Date(license.expires_at).toLocaleDateString()}</p>
              </div>
            </div>
            <div style={{ marginTop: '1.5rem' }}>
              <button onClick={validateLicense} disabled={validating} style={{ padding: '0.75rem 1.5rem', backgroundColor: '#d4af37', color: '#1a1a1a', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: validating ? 'not-allowed' : 'pointer', opacity: validating ? 0.6 : 1 }}>
                {validating ? 'Validating...' : 'Validate License'}
              </button>
            </div>
          </div>

          {license.features && license.features.length > 0 && (
            <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '2rem' }}>
              <h3 style={{ color: '#d4af37', marginBottom: '1rem' }}>Licensed Features</h3>
              <div style={{ display: 'grid', gap: '1rem' }}>
                {license.features.map((feature, idx) => (
                  <div key={idx} style={{ padding: '1rem', backgroundColor: '#1a1a1a', borderRadius: '4px', border: `1px solid ${feature.entitled ? '#4488ff' : '#444'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <h4 style={{ color: '#fff', marginBottom: '0.25rem' }}>{feature.name}</h4>
                        <p style={{ color: '#999', fontSize: '0.9rem' }}>{feature.description}</p>
                      </div>
                      <span style={{ padding: '0.5rem 1rem', borderRadius: '4px', backgroundColor: feature.entitled ? '#1a3a1a' : '#3a1a1a', color: feature.entitled ? '#44ff44' : '#ff4444', fontWeight: 'bold', fontSize: '0.9rem' }}>
                        {feature.entitled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '2rem', textAlign: 'center' }}>
          <p style={{ color: '#999' }}>No license information available</p>
        </div>
      )}
    </div>
  );
};

const SystemTab = () => {
  const [systemInfo, setSystemInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchSystemInfo = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/system/info', { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Failed to fetch system info');
      setSystemInfo(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSystemInfo(); }, []);

  return (
    <div>
      {error && <div style={{ backgroundColor: '#3a1a1a', border: '1px solid #ff4444', borderRadius: '4px', padding: '1rem', marginBottom: '1rem', color: '#ff6666' }}>{error}</div>}

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#999' }}>Loading...</div>
      ) : systemInfo ? (
        <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '2rem' }}>
          <pre style={{ backgroundColor: '#1a1a1a', padding: '1.5rem', borderRadius: '4px', color: '#fff', fontSize: '0.9rem', overflow: 'auto' }}>{JSON.stringify(systemInfo, null, 2)}</pre>
        </div>
      ) : (
        <div style={{ backgroundColor: '#2a2a2a', border: '1px solid #d4af37', borderRadius: '8px', padding: '2rem', textAlign: 'center' }}>
          <p style={{ color: '#999' }}>No system information available</p>
        </div>
      )}
    </div>
  );
};

export default Settings;

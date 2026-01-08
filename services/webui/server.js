import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000';
const NODE_ENV = process.env.NODE_ENV || 'development';

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// API proxy middleware
app.use('/api', createProxyMiddleware({
  target: API_BASE_URL,
  changeOrigin: true,
  pathRewrite: {
    '^/api': '/'
  },
  onError: (err, req, res) => {
    console.error('Proxy error:', err);
    res.status(503).json({ error: 'Backend service unavailable' });
  }
}));

// Health check endpoints
app.get('/healthz', (req, res) => {
  res.json({ status: 'ok' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'killkrill-webui' });
});

// Serve static files in production
if (NODE_ENV === 'production') {
  const buildPath = path.join(__dirname, 'dist');
  app.use(express.static(buildPath));

  // SPA fallback - send index.html for all unmatched routes
  app.get('*', (req, res) => {
    res.sendFile(path.join(buildPath, 'index.html'));
  });
} else {
  // In development, assume Vite dev server is running
  console.log('Development mode: Vite dev server should be running on port 5173');
  console.log(`API proxy configured to: ${API_BASE_URL}`);
}

// Error handling middleware
app.use((err, req, res, _next) => {
  console.error('Error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

const server = app.listen(PORT, () => {
  console.log(`Killkrill WebUI server running on port ${PORT}`);
  console.log(`Environment: ${NODE_ENV}`);
  console.log(`API Backend: ${API_BASE_URL}`);
});

export default server;

# Multi-stage build for KillKrill WebUI
FROM node:22-slim AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ALL dependencies (including devDependencies for build)
RUN npm ci

# Copy application code
COPY . .

# Build the React application
RUN npm run build

# Production stage
FROM node:22-slim

WORKDIR /app

# Create non-root user (use UID 1001 to avoid conflict with existing node user)
RUN groupadd -r webui && useradd -r -g webui -u 1001 webui

# Copy package files and install production dependencies only
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy built files from builder
COPY --from=builder --chown=webui:webui /app/dist ./dist

# Copy server.js
COPY --chown=webui:webui server.js ./

# Set production environment
ENV NODE_ENV=production
ENV PORT=3000

# Switch to non-root user
USER webui

# Expose port
EXPOSE 3000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"

# Start Express.js server
CMD ["node", "server.js"]

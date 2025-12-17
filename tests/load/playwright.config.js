/**
 * Playwright Configuration for Frontend Load/Smoke Tests
 *
 * Configures browser launch options, test timeouts, and reporting
 */

const config = {
  // Test timeout settings
  timeout: 30 * 1000, // 30 seconds per test
  expect: {
    timeout: 5 * 1000, // 5 seconds for assertions
  },

  // Browsers to use
  use: {
    // Base URL for all tests
    baseURL: process.env.FRONTEND_URL || 'http://localhost:3000',

    // Browser options
    headless: process.env.HEADLESS !== 'false',
    slowMo: process.env.SLOW_MO ? parseInt(process.env.SLOW_MO, 10) : 0,

    // Network settings
    bypassCSP: true,

    // Viewport size
    viewport: {
      width: 1280,
      height: 720,
    },

    // Emulation
    locale: 'en-US',
    timezone: 'UTC',

    // Video and screenshot settings
    screenshot: process.env.SCREENSHOT === 'true' ? 'only-on-failure' : 'off',
    video: process.env.VIDEO === 'true' ? 'retain-on-failure' : 'off',
    trace: process.env.TRACE === 'true' ? 'on-first-retry' : 'off',
  },

  // Test reporter - outputs to /tmp
  reporter: [
    ['html', { outputFolder: '/tmp/killkrill-tests/playwright-report' }],
    ['json', { outputFile: '/tmp/killkrill-tests/playwright-results.json' }],
    ['junit', { outputFile: '/tmp/killkrill-tests/playwright-results.xml' }],
    ['list'],
  ],

  // WebServer configuration (if needed)
  webServer: process.env.NO_SERVER === 'true' ? undefined : {
    command: process.env.SERVER_COMMAND || 'npm run dev',
    port: parseInt(process.env.PORT || '3000', 10),
    timeout: 120 * 1000,
    reuseExistingServer: !process.env.NO_REUSE_SERVER,
  },

  // Parallel execution
  fullyParallel: process.env.NO_PARALLEL === 'true' ? false : true,
  workers: process.env.WORKERS ? parseInt(process.env.WORKERS, 10) : undefined,

  // Retry settings
  retries: process.env.RETRIES ? parseInt(process.env.RETRIES, 10) : 2,
};

module.exports = config;

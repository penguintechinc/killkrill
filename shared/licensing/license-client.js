/**
 * Killkrill License Client - JavaScript/Node.js
 *
 * Integrates with PenguinTech License Server for feature gating
 * https://license.penguintech.io
 */

const LICENSE_SERVER_URL =
  process.env.LICENSE_SERVER_URL || "https://license.penguintech.io";
const PRODUCT_NAME = process.env.PRODUCT_NAME || "killkrill";

/**
 * License client for killkrill
 */
class LicenseClient {
  constructor(licenseKey = null, baseUrl = null) {
    this.licenseKey = licenseKey || process.env.LICENSE_KEY;
    this.baseUrl = baseUrl || LICENSE_SERVER_URL;
    this.productName = PRODUCT_NAME;
    this.releaseMode = process.env.RELEASE_MODE === "true";
    this.cache = new Map();
    this.cacheTimeout = 300000; // 5 minutes
  }

  /**
   * Validate license key format
   * @param {string} key - License key to validate
   * @returns {boolean} True if format is valid
   */
  isValidFormat(key) {
    if (!key || typeof key !== "string") return false;
    return /^PENG-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(
      key,
    );
  }

  /**
   * Validate license with server
   * @returns {Promise<Object>} License validation response
   */
  async validate() {
    // In development mode, skip validation
    if (!this.releaseMode) {
      return {
        valid: true,
        tier: "enterprise",
        features: ["all"],
        message: "Development mode - all features enabled",
      };
    }

    if (!this.licenseKey) {
      throw new Error("License key not provided");
    }

    if (!this.isValidFormat(this.licenseKey)) {
      throw new Error("Invalid license key format");
    }

    const response = await fetch(`${this.baseUrl}/api/v2/validate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        license_key: this.licenseKey,
        product: this.productName,
      }),
    });

    if (!response.ok) {
      throw new Error(`License validation failed: ${response.status}`);
    }

    const data = await response.json();
    if (!data.valid) {
      throw new Error(data.message || "License validation failed");
    }

    return data;
  }

  /**
   * Check if a feature is available
   * @param {string} featureName - Feature to check
   * @returns {Promise<boolean>} True if feature is available
   */
  async hasFeature(featureName) {
    // In development mode, all features available
    if (!this.releaseMode) {
      return true;
    }

    // Check cache first
    const cacheKey = `feature:${featureName}`;
    if (this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey);
      if (Date.now() - cached.timestamp < this.cacheTimeout) {
        return cached.value;
      }
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/v2/features`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          license_key: this.licenseKey,
          product: this.productName,
          feature: featureName,
        }),
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      const hasFeature = data.available === true;

      // Cache result
      this.cache.set(cacheKey, {
        value: hasFeature,
        timestamp: Date.now(),
      });

      return hasFeature;
    } catch (error) {
      console.error(`Feature check failed for ${featureName}:`, error);
      return false;
    }
  }

  /**
   * Send keepalive/heartbeat to license server
   * @param {Object} stats - Optional usage statistics
   * @returns {Promise<Object>} Keepalive response
   */
  async keepalive(stats = {}) {
    if (!this.releaseMode) {
      return { success: true };
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/v2/keepalive`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          license_key: this.licenseKey,
          product: this.productName,
          stats: stats,
          timestamp: new Date().toISOString(),
        }),
      });

      if (!response.ok) {
        throw new Error(`Keepalive failed: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("License keepalive failed:", error);
      throw error;
    }
  }

  /**
   * Clear the feature cache
   */
  clearCache() {
    this.cache.clear();
  }
}

/**
 * Singleton instance
 */
let clientInstance = null;

/**
 * Get or create license client instance
 * @param {string} licenseKey - Optional license key
 * @returns {LicenseClient} License client instance
 */
function getLicenseClient(licenseKey = null) {
  if (!clientInstance) {
    clientInstance = new LicenseClient(licenseKey);
  }
  return clientInstance;
}

/**
 * Decorator function to require a feature
 * @param {string} featureName - Required feature name
 * @returns {Function} Decorator function
 */
function requiresFeature(featureName) {
  return function (target, propertyKey, descriptor) {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args) {
      const client = getLicenseClient();
      const hasFeature = await client.hasFeature(featureName);

      if (!hasFeature) {
        throw new Error(
          `Feature '${featureName}' not available with current license`,
        );
      }

      return originalMethod.apply(this, args);
    };

    return descriptor;
  };
}

module.exports = {
  LicenseClient,
  getLicenseClient,
  requiresFeature,
  LICENSE_SERVER_URL,
};

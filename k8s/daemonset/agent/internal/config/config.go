package config

import (
	"fmt"
	"os"
	"strconv"
	"time"

	"gopkg.in/yaml.v3"
)

// Config represents the complete configuration for the KillKrill agent
type Config struct {
	Agent       AgentConfig       `yaml:"agent"`
	Logs        LogsConfig        `yaml:"logs"`
	Metrics     MetricsConfig     `yaml:"metrics"`
	Health      HealthConfig      `yaml:"health"`
	Security    SecurityConfig    `yaml:"security"`
	Performance PerformanceConfig `yaml:"performance"`
	Logging     LoggingConfig     `yaml:"logging"`
}

// AgentConfig contains basic agent configuration
type AgentConfig struct {
	NodeName    string `yaml:"node_name"`
	NodeIP      string `yaml:"node_ip"`
	ClusterName string `yaml:"cluster_name"`
}

// LogsConfig contains log collection configuration
type LogsConfig struct {
	Enabled           bool                     `yaml:"enabled"`
	Paths             []string                 `yaml:"paths"`
	ContainerRuntimes []string                 `yaml:"container_runtimes"`
	Parsers           []ParserConfig           `yaml:"parsers"`
	Kubernetes        KubernetesEnrichConfig   `yaml:"kubernetes"`
	Output            OutputConfig             `yaml:"output"`
}

// MetricsConfig contains metrics collection configuration
type MetricsConfig struct {
	Enabled    bool                     `yaml:"enabled"`
	Interval   string                   `yaml:"interval"`
	Sources    []MetricSourceConfig     `yaml:"sources"`
	Kubernetes KubernetesEnrichConfig   `yaml:"kubernetes"`
	Output     OutputConfig             `yaml:"output"`
}

// ParserConfig defines how to parse logs
type ParserConfig struct {
	Name       string `yaml:"name"`
	Format     string `yaml:"format"`
	TimeKey    string `yaml:"time_key"`
	TimeFormat string `yaml:"time_format"`
}

// MetricSourceConfig defines a metrics source
type MetricSourceConfig struct {
	Name     string `yaml:"name"`
	URL      string `yaml:"url"`
	CertFile string `yaml:"cert_file"`
	KeyFile  string `yaml:"key_file"`
	CAFile   string `yaml:"ca_file"`
	Optional bool   `yaml:"optional"`
}

// KubernetesEnrichConfig contains Kubernetes metadata enrichment configuration
type KubernetesEnrichConfig struct {
	Enabled              bool     `yaml:"enabled"`
	PodMetadata          []string `yaml:"pod_metadata"`
	NodeMetadata         []string `yaml:"node_metadata"`
	EnrichPodMetrics     bool     `yaml:"enrich_pod_metrics"`
	EnrichNodeMetrics    bool     `yaml:"enrich_node_metrics"`
	EnrichContainerMetrics bool   `yaml:"enrich_container_metrics"`
}

// OutputConfig contains output destination configuration
type OutputConfig struct {
	Type            string            `yaml:"type"`
	URL             string            `yaml:"url"`
	Headers         map[string]string `yaml:"headers"`
	BatchSize       int               `yaml:"batch_size"`
	FlushInterval   string            `yaml:"flush_interval"`
	Compression     string            `yaml:"compression"`
	RetryAttempts   int               `yaml:"retry_attempts"`
	RetryBackoff    string            `yaml:"retry_backoff"`
}

// HealthConfig contains health server configuration
type HealthConfig struct {
	BindAddress string `yaml:"bind_address"`
	MetricsPath string `yaml:"metrics_path"`
	HealthPath  string `yaml:"health_path"`
	ReadyPath   string `yaml:"ready_path"`
}

// SecurityConfig contains security settings
type SecurityConfig struct {
	TLS TLSConfig `yaml:"tls"`
}

// TLSConfig contains TLS configuration
type TLSConfig struct {
	Enabled          bool     `yaml:"enabled"`
	CertFile         string   `yaml:"cert_file"`
	KeyFile          string   `yaml:"key_file"`
	CAFile           string   `yaml:"ca_file"`
	VerifyServerCert bool     `yaml:"verify_server_cert"`
	MinVersion       string   `yaml:"min_version"`
	CipherSuites     []string `yaml:"cipher_suites"`
}

// PerformanceConfig contains performance tuning settings
type PerformanceConfig struct {
	WorkerThreads       int    `yaml:"worker_threads"`
	BufferSize          string `yaml:"buffer_size"`
	QueueSize           int    `yaml:"queue_size"`
	CompressionLevel    int    `yaml:"compression_level"`
	BatchTimeout        string `yaml:"batch_timeout"`
	ConnectionPoolSize  int    `yaml:"connection_pool_size"`
	KeepAliveTimeout    string `yaml:"keep_alive_timeout"`
}

// LoggingConfig contains logging configuration
type LoggingConfig struct {
	Level  string            `yaml:"level"`
	Format string            `yaml:"format"`
	Output string            `yaml:"output"`
	Fields map[string]string `yaml:"fields"`
}

// Load loads configuration from environment variables and config file
func Load() (*Config, error) {
	// Default configuration
	cfg := &Config{
		Agent: AgentConfig{
			NodeName:    getEnv("NODE_NAME", "unknown"),
			NodeIP:      getEnv("NODE_IP", "unknown"),
			ClusterName: getEnv("CLUSTER_NAME", "default"),
		},
		Logs: LogsConfig{
			Enabled: getBoolEnv("LOGS_ENABLED", true),
			Paths: []string{
				"/var/log/pods/*/*/*.log",
				"/var/log/containers/*.log",
			},
			ContainerRuntimes: []string{"docker", "containerd", "cri-o"},
			Output: OutputConfig{
				Type:          "http3",
				URL:           getEnv("KILLKRILL_LOG_RECEIVER_URL", ""),
				BatchSize:     getIntEnv("LOG_BATCH_SIZE", 1000),
				FlushInterval: getEnv("LOG_FLUSH_INTERVAL", "5s"),
				Compression:   "gzip",
				RetryAttempts: 3,
				RetryBackoff:  "1s",
			},
		},
		Metrics: MetricsConfig{
			Enabled:  getBoolEnv("METRICS_ENABLED", true),
			Interval: getEnv("METRICS_INTERVAL", "30s"),
			Output: OutputConfig{
				Type:          "http3",
				URL:           getEnv("KILLKRILL_METRICS_RECEIVER_URL", ""),
				BatchSize:     getIntEnv("METRICS_BATCH_SIZE", 500),
				FlushInterval: getEnv("METRICS_FLUSH_INTERVAL", "30s"),
				Compression:   "gzip",
				RetryAttempts: 3,
				RetryBackoff:  "2s",
			},
		},
		Health: HealthConfig{
			BindAddress: getEnv("HEALTH_BIND_ADDRESS", "0.0.0.0:8080"),
			MetricsPath: "/metrics",
			HealthPath:  "/healthz",
			ReadyPath:   "/ready",
		},
		Security: SecurityConfig{
			TLS: TLSConfig{
				Enabled:          getBoolEnv("TLS_ENABLED", true),
				VerifyServerCert: getBoolEnv("TLS_VERIFY_SERVER", false),
				MinVersion:       "1.2",
			},
		},
		Performance: PerformanceConfig{
			WorkerThreads:      getIntEnv("WORKER_THREADS", 4),
			BufferSize:         getEnv("BUFFER_SIZE", "16MB"),
			QueueSize:          getIntEnv("QUEUE_SIZE", 10000),
			CompressionLevel:   getIntEnv("COMPRESSION_LEVEL", 6),
			BatchTimeout:       getEnv("BATCH_TIMEOUT", "1s"),
			ConnectionPoolSize: getIntEnv("CONNECTION_POOL_SIZE", 10),
			KeepAliveTimeout:   getEnv("KEEP_ALIVE_TIMEOUT", "30s"),
		},
		Logging: LoggingConfig{
			Level:  getEnv("LOG_LEVEL", "info"),
			Format: getEnv("LOG_FORMAT", "json"),
			Output: getEnv("LOG_OUTPUT", "stdout"),
			Fields: map[string]string{
				"service": "killkrill-agent",
				"version": "v1.0.0",
				"cluster": getEnv("CLUSTER_NAME", "default"),
				"node":    getEnv("NODE_NAME", "unknown"),
			},
		},
	}

	// Load additional configuration from file if it exists
	configFile := getEnv("CONFIG_FILE", "/etc/killkrill/config.yaml")
	if _, err := os.Stat(configFile); err == nil {
		if err := loadConfigFile(cfg, configFile); err != nil {
			return nil, fmt.Errorf("failed to load config file %s: %w", configFile, err)
		}
	}

	// Apply environment variable overrides
	if err := applyEnvOverrides(cfg); err != nil {
		return nil, fmt.Errorf("failed to apply environment overrides: %w", err)
	}

	// Validate configuration
	if err := validate(cfg); err != nil {
		return nil, fmt.Errorf("configuration validation failed: %w", err)
	}

	return cfg, nil
}

func loadConfigFile(cfg *Config, filename string) error {
	data, err := os.ReadFile(filename)
	if err != nil {
		return err
	}

	// Expand environment variables in config file
	expanded := os.ExpandEnv(string(data))

	return yaml.Unmarshal([]byte(expanded), cfg)
}

func applyEnvOverrides(cfg *Config) error {
	// Set up headers with license key
	licenseKey := getEnv("KILLKRILL_LICENSE_KEY", "")
	if licenseKey != "" {
		if cfg.Logs.Output.Headers == nil {
			cfg.Logs.Output.Headers = make(map[string]string)
		}
		if cfg.Metrics.Output.Headers == nil {
			cfg.Metrics.Output.Headers = make(map[string]string)
		}

		cfg.Logs.Output.Headers["Authorization"] = "Bearer " + licenseKey
		cfg.Logs.Output.Headers["X-Cluster-Name"] = cfg.Agent.ClusterName

		cfg.Metrics.Output.Headers["Authorization"] = "Bearer " + licenseKey
		cfg.Metrics.Output.Headers["X-Cluster-Name"] = cfg.Agent.ClusterName
	}

	return nil
}

func validate(cfg *Config) error {
	if cfg.Agent.NodeName == "" {
		return fmt.Errorf("agent.node_name is required")
	}

	if cfg.Agent.ClusterName == "" {
		return fmt.Errorf("agent.cluster_name is required")
	}

	if cfg.Logs.Enabled && cfg.Logs.Output.URL == "" {
		return fmt.Errorf("logs.output.url is required when logs are enabled")
	}

	if cfg.Metrics.Enabled && cfg.Metrics.Output.URL == "" {
		return fmt.Errorf("metrics.output.url is required when metrics are enabled")
	}

	// Validate intervals
	if cfg.Metrics.Enabled {
		if _, err := time.ParseDuration(cfg.Metrics.Interval); err != nil {
			return fmt.Errorf("invalid metrics.interval: %w", err)
		}
	}

	if _, err := time.ParseDuration(cfg.Logs.Output.FlushInterval); err != nil {
		return fmt.Errorf("invalid logs.output.flush_interval: %w", err)
	}

	if _, err := time.ParseDuration(cfg.Metrics.Output.FlushInterval); err != nil {
		return fmt.Errorf("invalid metrics.output.flush_interval: %w", err)
	}

	return nil
}

// Helper functions for environment variable handling
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getBoolEnv(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if parsed, err := strconv.ParseBool(value); err == nil {
			return parsed
		}
	}
	return defaultValue
}

func getIntEnv(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if parsed, err := strconv.Atoi(value); err == nil {
			return parsed
		}
	}
	return defaultValue
}
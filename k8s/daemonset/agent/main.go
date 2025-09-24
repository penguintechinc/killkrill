package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/collector"
	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/config"
	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/health"
	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/kubernetes"
	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/logs"
	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/metrics"
	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/sender"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"
)

var (
	// Build information - set by linker
	Version   = "dev"
	GitCommit = "unknown"
	BuildTime = "unknown"

	// Prometheus metrics
	agentStartTime = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "killkrill_agent_start_time_seconds",
			Help: "Start time of the agent in seconds since epoch",
		},
		[]string{"node", "cluster"},
	)

	agentInfo = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "killkrill_agent_info",
			Help: "Information about the KillKrill agent",
		},
		[]string{"version", "git_commit", "build_time", "node", "cluster"},
	)
)

func init() {
	prometheus.MustRegister(agentStartTime)
	prometheus.MustRegister(agentInfo)
}

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Setup logging
	setupLogging(cfg)

	logrus.WithFields(logrus.Fields{
		"version":    Version,
		"git_commit": GitCommit,
		"build_time": BuildTime,
		"node":       cfg.Agent.NodeName,
		"cluster":    cfg.Agent.ClusterName,
	}).Info("KillKrill Agent starting")

	// Update Prometheus metrics
	agentStartTime.WithLabelValues(cfg.Agent.NodeName, cfg.Agent.ClusterName).SetToCurrentTime()
	agentInfo.WithLabelValues(Version, GitCommit, BuildTime, cfg.Agent.NodeName, cfg.Agent.ClusterName).Set(1)

	// Create context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Setup signal handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Initialize Kubernetes client
	k8sClient, err := kubernetes.NewClient(cfg)
	if err != nil {
		logrus.Fatalf("Failed to create Kubernetes client: %v", err)
	}

	// Initialize HTTP3/QUIC senders
	logSender, err := sender.NewHTTP3Sender(cfg.Logs.Output, "logs")
	if err != nil {
		logrus.Fatalf("Failed to create log sender: %v", err)
	}

	metricsSender, err := sender.NewHTTP3Sender(cfg.Metrics.Output, "metrics")
	if err != nil {
		logrus.Fatalf("Failed to create metrics sender: %v", err)
	}

	// Initialize collectors
	var wg sync.WaitGroup
	var collectors []collector.Collector

	// Log collector
	if cfg.Logs.Enabled {
		logCollector, err := logs.NewCollector(cfg, k8sClient, logSender)
		if err != nil {
			logrus.Fatalf("Failed to create log collector: %v", err)
		}
		collectors = append(collectors, logCollector)
	}

	// Metrics collector
	if cfg.Metrics.Enabled {
		metricsCollector, err := metrics.NewCollector(cfg, k8sClient, metricsSender)
		if err != nil {
			logrus.Fatalf("Failed to create metrics collector: %v", err)
		}
		collectors = append(collectors, metricsCollector)
	}

	// Start health server
	healthServer := health.NewServer(cfg.Health, collectors)
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := healthServer.Start(ctx); err != nil {
			logrus.Errorf("Health server error: %v", err)
		}
	}()

	// Start all collectors
	for _, c := range collectors {
		wg.Add(1)
		go func(collector collector.Collector) {
			defer wg.Done()
			if err := collector.Start(ctx); err != nil {
				logrus.Errorf("Collector %s error: %v", collector.Name(), err)
			}
		}(c)
	}

	logrus.Info("KillKrill Agent started successfully")

	// Wait for shutdown signal
	select {
	case sig := <-sigChan:
		logrus.WithField("signal", sig).Info("Received shutdown signal")
	case <-ctx.Done():
		logrus.Info("Context cancelled")
	}

	// Graceful shutdown
	logrus.Info("Shutting down KillKrill Agent...")

	// Cancel context to signal all goroutines to stop
	cancel()

	// Wait for all collectors and servers to shutdown with timeout
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		logrus.Info("All components shut down successfully")
	case <-time.After(30 * time.Second):
		logrus.Warn("Shutdown timeout exceeded, forcing exit")
	}

	// Close senders
	logSender.Close()
	metricsSender.Close()

	logrus.Info("KillKrill Agent shutdown complete")
}

func setupLogging(cfg *config.Config) {
	// Set log level
	level, err := logrus.ParseLevel(cfg.Logging.Level)
	if err != nil {
		logrus.Warnf("Invalid log level '%s', using info", cfg.Logging.Level)
		level = logrus.InfoLevel
	}
	logrus.SetLevel(level)

	// Set log format
	switch cfg.Logging.Format {
	case "json":
		logrus.SetFormatter(&logrus.JSONFormatter{
			TimestampFormat: time.RFC3339Nano,
			FieldMap: logrus.FieldMap{
				logrus.FieldKeyTime:  "timestamp",
				logrus.FieldKeyLevel: "level",
				logrus.FieldKeyMsg:   "message",
			},
		})
	default:
		logrus.SetFormatter(&logrus.TextFormatter{
			FullTimestamp:   true,
			TimestampFormat: time.RFC3339,
		})
	}

	// Add common fields
	logrus.SetReportCaller(false)

	// Add structured fields if configured
	if len(cfg.Logging.Fields) > 0 {
		logrus.WithFields(logrus.Fields(cfg.Logging.Fields))
	}
}
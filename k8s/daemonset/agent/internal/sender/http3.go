package sender

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/penguintechinc/killkrill/k8s/daemonset/agent/internal/config"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"
	"github.com/quic-go/quic-go"
	"github.com/quic-go/quic-go/http3"
)

var (
	// Prometheus metrics
	sentBytes = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "killkrill_agent_sent_bytes_total",
			Help: "Total bytes sent to KillKrill receivers",
		},
		[]string{"type", "status"},
	)

	sentMessages = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "killkrill_agent_sent_messages_total",
			Help: "Total messages sent to KillKrill receivers",
		},
		[]string{"type", "status"},
	)

	sendDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "killkrill_agent_send_duration_seconds",
			Help:    "Duration of send operations",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"type", "protocol"},
	)

	batchSize = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "killkrill_agent_batch_size",
			Help:    "Size of batches sent to receivers",
			Buckets: []float64{1, 10, 50, 100, 500, 1000, 2000, 5000},
		},
		[]string{"type"},
	)

	protocolFallbacks = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "killkrill_agent_protocol_fallbacks_total",
			Help: "Total number of protocol fallbacks from HTTP3 to HTTP1.1",
		},
		[]string{"type", "reason"},
	)

	currentProtocol = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "killkrill_agent_current_protocol",
			Help: "Current protocol in use (3 for HTTP3, 1 for HTTP1.1)",
		},
		[]string{"type"},
	)
)

func init() {
	prometheus.MustRegister(sentBytes)
	prometheus.MustRegister(sentMessages)
	prometheus.MustRegister(sendDuration)
	prometheus.MustRegister(batchSize)
	prometheus.MustRegister(protocolFallbacks)
	prometheus.MustRegister(currentProtocol)
}

// Message represents a message to be sent
type Message struct {
	Data      interface{} `json:"data"`
	Timestamp time.Time   `json:"timestamp"`
	Type      string      `json:"type"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// HTTP3Sender sends messages using HTTP3/QUIC protocol with HTTP1.1 fallback
type HTTP3Sender struct {
	config       config.OutputConfig
	http3Client  *http.Client
	http1Client  *http.Client
	dataType     string
	batchCh      chan *Message
	stopCh       chan struct{}
	wg           sync.WaitGroup
	logger       *logrus.Entry
	useHTTP3     bool
	fallbackMutex sync.RWMutex
	fallbackURL  string
	lastFallback time.Time
}

// NewHTTP3Sender creates a new HTTP3 sender with HTTP1.1 fallback
func NewHTTP3Sender(cfg config.OutputConfig, dataType string) (*HTTP3Sender, error) {
	// Create shared TLS config
	tlsConfig := &tls.Config{
		InsecureSkipVerify: true, // Allow self-signed certs in dev
		NextProtos:         []string{"h3", "h2", "http/1.1"},
	}

	// Create HTTP3/QUIC client
	quicConfig := &quic.Config{
		KeepAlivePeriod: 30 * time.Second,
		MaxIdleTimeout:  60 * time.Second,
	}

	http3RoundTripper := &http3.RoundTripper{
		TLSClientConfig: tlsConfig,
		QuicConfig:      quicConfig,
	}

	http3Client := &http.Client{
		Transport: http3RoundTripper,
		Timeout:   30 * time.Second,
	}

	// Create HTTP1.1 fallback client
	http1Transport := &http.Transport{
		TLSClientConfig: tlsConfig,
		DialContext: (&net.Dialer{
			Timeout:   10 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 10,
		IdleConnTimeout:     90 * time.Second,
		DisableCompression:  false,
	}

	http1Client := &http.Client{
		Transport: http1Transport,
		Timeout:   30 * time.Second,
	}

	// Generate fallback URL (convert HTTP3/QUIC port to py4web port)
	fallbackURL := cfg.URL

	// Convert QUIC ports to py4web HTTP port (8000)
	if strings.Contains(cfg.URL, ":8443") {
		fallbackURL = strings.Replace(cfg.URL, ":8443", ":8000", 1)
	} else if strings.Contains(cfg.URL, ":8444") {
		fallbackURL = strings.Replace(cfg.URL, ":8444", ":8000", 1)
	}

	// Add py4web API endpoint paths
	if strings.Contains(fallbackURL, "log-receiver") {
		// Convert to py4web log ingestion endpoint
		fallbackURL += "/api/v1/logs/ingest"
	} else if strings.Contains(fallbackURL, "metrics-receiver") {
		// Convert to py4web metrics ingestion endpoint
		fallbackURL += "/api/v1/metrics/ingest"
	}

	// Keep HTTPS for py4web (it can handle TLS too)
	// But allow HTTP if explicitly configured for development

	sender := &HTTP3Sender{
		config:      cfg,
		http3Client: http3Client,
		http1Client: http1Client,
		dataType:    dataType,
		batchCh:     make(chan *Message, cfg.BatchSize*2),
		stopCh:      make(chan struct{}),
		logger:      logrus.WithField("component", fmt.Sprintf("adaptive_sender_%s", dataType)),
		useHTTP3:    true, // Start with HTTP3
		fallbackURL: fallbackURL,
	}

	// Set initial protocol metric
	currentProtocol.WithLabelValues(dataType).Set(3)

	sender.logger.WithFields(logrus.Fields{
		"http3_url":    cfg.URL,
		"fallback_url": fallbackURL,
	}).Info("Adaptive sender initialized with HTTP3 primary and HTTP1.1 fallback")

	// Start batch processor
	sender.wg.Add(1)
	go sender.batchProcessor()

	return sender, nil
}

// Send queues a message for sending
func (s *HTTP3Sender) Send(data interface{}, metadata map[string]interface{}) error {
	msg := &Message{
		Data:      data,
		Timestamp: time.Now(),
		Type:      s.dataType,
		Metadata:  metadata,
	}

	select {
	case s.batchCh <- msg:
		return nil
	default:
		s.logger.Warn("Send buffer full, dropping message")
		sentMessages.WithLabelValues(s.dataType, "dropped").Inc()
		return fmt.Errorf("send buffer full")
	}
}

// Close gracefully shuts down the sender
func (s *HTTP3Sender) Close() {
	close(s.stopCh)
	s.wg.Wait()

	// Close HTTP3 transport
	if roundTripper, ok := s.http3Client.Transport.(*http3.RoundTripper); ok {
		roundTripper.Close()
	}
}

// batchProcessor processes batches of messages
func (s *HTTP3Sender) batchProcessor() {
	defer s.wg.Done()

	flushInterval, err := time.ParseDuration(s.config.FlushInterval)
	if err != nil {
		s.logger.Errorf("Invalid flush interval %s, using 5s", s.config.FlushInterval)
		flushInterval = 5 * time.Second
	}

	ticker := time.NewTicker(flushInterval)
	defer ticker.Stop()

	batch := make([]*Message, 0, s.config.BatchSize)

	for {
		select {
		case msg := <-s.batchCh:
			batch = append(batch, msg)
			if len(batch) >= s.config.BatchSize {
				s.sendBatch(batch)
				batch = batch[:0] // Reset slice but keep capacity
			}

		case <-ticker.C:
			if len(batch) > 0 {
				s.sendBatch(batch)
				batch = batch[:0]
			}

		case <-s.stopCh:
			// Send remaining messages
			if len(batch) > 0 {
				s.sendBatch(batch)
			}
			return
		}
	}
}

// sendBatch sends a batch of messages
func (s *HTTP3Sender) sendBatch(batch []*Message) {
	if len(batch) == 0 {
		return
	}

	start := time.Now()
	var protocol string

	batchSize.WithLabelValues(s.dataType).Observe(float64(len(batch)))

	// Prepare payload
	payload := map[string]interface{}{
		"messages": batch,
		"batch_id": fmt.Sprintf("%s-%d", s.dataType, time.Now().UnixNano()),
		"count":    len(batch),
	}

	// Serialize to JSON
	jsonData, err := json.Marshal(payload)
	if err != nil {
		s.logger.Errorf("Failed to marshal batch: %v", err)
		sentMessages.WithLabelValues(s.dataType, "marshal_error").Add(float64(len(batch)))
		return
	}

	// Compress if enabled
	var body io.Reader = bytes.NewReader(jsonData)
	var contentEncoding string

	if s.config.Compression == "gzip" {
		var buf bytes.Buffer
		gzipWriter := gzip.NewWriter(&buf)
		if _, err := gzipWriter.Write(jsonData); err != nil {
			s.logger.Errorf("Failed to compress batch: %v", err)
			sentMessages.WithLabelValues(s.dataType, "compression_error").Add(float64(len(batch)))
			return
		}
		gzipWriter.Close()
		body = bytes.NewReader(buf.Bytes())
		contentEncoding = "gzip"
	}

	// Send with retries and protocol fallback
	if err := s.sendWithFallback(body, contentEncoding, len(batch)); err != nil {
		s.logger.Errorf("Failed to send batch after retries and fallback: %v", err)
		sentMessages.WithLabelValues(s.dataType, "failed").Add(float64(len(batch)))
		protocol = "failed"
	} else {
		sentMessages.WithLabelValues(s.dataType, "success").Add(float64(len(batch)))
		sentBytes.WithLabelValues(s.dataType, "success").Add(float64(len(jsonData)))

		s.fallbackMutex.RLock()
		if s.useHTTP3 {
			protocol = "http3"
		} else {
			protocol = "http1.1"
		}
		s.fallbackMutex.RUnlock()
	}

	// Record duration with protocol label
	sendDuration.WithLabelValues(s.dataType, protocol).Observe(time.Since(start).Seconds())
}

// sendWithFallback sends data with retry logic and HTTP1.1 fallback
func (s *HTTP3Sender) sendWithFallback(body io.Reader, contentEncoding string, messageCount int) error {
	backoffDuration, err := time.ParseDuration(s.config.RetryBackoff)
	if err != nil {
		backoffDuration = time.Second
	}

	// Try HTTP3 first if enabled
	s.fallbackMutex.RLock()
	useHTTP3 := s.useHTTP3
	s.fallbackMutex.RUnlock()

	if useHTTP3 {
		if err := s.sendWithProtocol(s.http3Client, s.config.URL, body, contentEncoding, messageCount, "HTTP3"); err != nil {
			s.logger.WithError(err).Warn("HTTP3 send failed, falling back to HTTP1.1")

			// Mark fallback and update metrics
			s.fallbackMutex.Lock()
			s.useHTTP3 = false
			s.lastFallback = time.Now()
			s.fallbackMutex.Unlock()

			currentProtocol.WithLabelValues(s.dataType).Set(1)
			protocolFallbacks.WithLabelValues(s.dataType, "http3_failed").Inc()

			// Reset body reader for retry
			if seeker, ok := body.(io.Seeker); ok {
				seeker.Seek(0, io.SeekStart)
			}
		} else {
			return nil // HTTP3 success
		}
	}

	// Try HTTP1.1 fallback
	if err := s.sendWithProtocol(s.http1Client, s.fallbackURL, body, contentEncoding, messageCount, "HTTP1.1"); err != nil {
		return fmt.Errorf("both HTTP3 and HTTP1.1 failed: %w", err)
	}

	// Check if we should retry HTTP3 after some time
	s.fallbackMutex.RLock()
	lastFallback := s.lastFallback
	s.fallbackMutex.RUnlock()

	if time.Since(lastFallback) > 5*time.Minute {
		s.logger.Info("Attempting to restore HTTP3 connection")
		s.fallbackMutex.Lock()
		s.useHTTP3 = true
		s.fallbackMutex.Unlock()
		currentProtocol.WithLabelValues(s.dataType).Set(3)
	}

	return nil
}

// sendWithProtocol sends data with a specific protocol client
func (s *HTTP3Sender) sendWithProtocol(client *http.Client, url string, body io.Reader, contentEncoding string, messageCount int, protocolName string) error {
	var lastErr error

	backoffDuration, err := time.ParseDuration(s.config.RetryBackoff)
	if err != nil {
		backoffDuration = time.Second
	}

	for attempt := 0; attempt <= s.config.RetryAttempts; attempt++ {
		if attempt > 0 {
			s.logger.Debugf("%s retry attempt %d/%d", protocolName, attempt, s.config.RetryAttempts)
			time.Sleep(backoffDuration * time.Duration(attempt))

			// Reset body reader for retry
			if seeker, ok := body.(io.Seeker); ok {
				seeker.Seek(0, io.SeekStart)
			}
		}

		// Create request
		req, err := http.NewRequest("POST", url, body)
		if err != nil {
			lastErr = fmt.Errorf("failed to create %s request: %w", protocolName, err)
			continue
		}

		// Set headers
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("User-Agent", "KillKrill-Agent/1.0")
		req.Header.Set("X-Batch-Size", fmt.Sprintf("%d", messageCount))
		req.Header.Set("X-Protocol", protocolName)

		if contentEncoding != "" {
			req.Header.Set("Content-Encoding", contentEncoding)
		}

		// Set custom headers from config
		for key, value := range s.config.Headers {
			req.Header.Set(key, value)
		}

		// Send request
		resp, err := client.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("%s request failed: %w", protocolName, err)

			// For HTTP3, certain errors indicate protocol unavailability
			if protocolName == "HTTP3" && isHTTP3UnavailableError(err) {
				return fmt.Errorf("HTTP3 unavailable: %w", err)
			}
			continue
		}

		// Check response
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			resp.Body.Close()
			s.logger.Debugf("%s send successful to %s", protocolName, url)
			return nil
		}

		// Read error response
		bodyBytes, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		lastErr = fmt.Errorf("%s server returned %d: %s", protocolName, resp.StatusCode, string(bodyBytes))

		// Don't retry on client errors (4xx)
		if resp.StatusCode >= 400 && resp.StatusCode < 500 {
			break
		}
	}

	return lastErr
}

// isHTTP3UnavailableError checks if the error indicates HTTP3/QUIC is unavailable
func isHTTP3UnavailableError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// Common HTTP3/QUIC unavailability indicators
	indicators := []string{
		"no such host",
		"connection refused",
		"protocol not supported",
		"quic",
		"udp",
		"timeout",
		"network unreachable",
	}

	for _, indicator := range indicators {
		if strings.Contains(strings.ToLower(errStr), indicator) {
			return true
		}
	}

	return false
}

// Health returns the health status of the sender
func (s *HTTP3Sender) Health() map[string]interface{} {
	s.fallbackMutex.RLock()
	currentProtocol := "HTTP3"
	if !s.useHTTP3 {
		currentProtocol = "HTTP1.1"
	}
	lastFallback := s.lastFallback
	s.fallbackMutex.RUnlock()

	return map[string]interface{}{
		"type":         "adaptive_sender",
		"data_type":    s.dataType,
		"http3_url":    s.config.URL,
		"fallback_url": s.fallbackURL,
		"current_protocol": currentProtocol,
		"last_fallback":    lastFallback,
		"buffer_size":  len(s.batchCh),
		"buffer_cap":   cap(s.batchCh),
		"compression":  s.config.Compression,
		"batch_size":   s.config.BatchSize,
		"retry_config": map[string]interface{}{
			"attempts": s.config.RetryAttempts,
			"backoff":  s.config.RetryBackoff,
		},
	}
}
package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	corev1 "k8s.io/api/core/v1"
)

// EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!
// NOTE: json tags are required.  Any new fields you add must have json tags for the fields to be serialized.

// KillKrillSpec defines the desired state of KillKrill
type KillKrillSpec struct {
	// INSERT ADDITIONAL SPEC FIELDS - desired state of cluster
	// Important: Run "make" to regenerate code after modifying this file

	// Size defines the number of replicas for each component
	Size int32 `json:"size,omitempty"`

	// License configuration
	License LicenseConfig `json:"license"`

	// Infrastructure configuration
	Infrastructure InfrastructureConfig `json:"infrastructure"`

	// Application configuration
	Applications ApplicationConfig `json:"applications"`

	// Monitoring configuration
	Monitoring MonitoringConfig `json:"monitoring,omitempty"`

	// Storage configuration
	Storage StorageConfig `json:"storage,omitempty"`

	// Security configuration
	Security SecurityConfig `json:"security,omitempty"`
}

// LicenseConfig defines the license configuration
type LicenseConfig struct {
	// License key for PenguinTech services
	Key string `json:"key"`

	// Product name
	Product string `json:"product,omitempty"`

	// License server URL
	Server string `json:"server,omitempty"`
}

// InfrastructureConfig defines the infrastructure components
type InfrastructureConfig struct {
	// PostgreSQL configuration
	PostgreSQL PostgreSQLConfig `json:"postgresql"`

	// Redis configuration
	Redis RedisConfig `json:"redis"`

	// Elasticsearch configuration
	Elasticsearch ElasticsearchConfig `json:"elasticsearch"`

	// Prometheus configuration
	Prometheus PrometheusConfig `json:"prometheus"`

	// Grafana configuration
	Grafana GrafanaConfig `json:"grafana,omitempty"`
}

// PostgreSQLConfig defines PostgreSQL settings
type PostgreSQLConfig struct {
	// Database name
	Database string `json:"database,omitempty"`

	// Username
	Username string `json:"username,omitempty"`

	// Password (should be stored in secret)
	PasswordSecret string `json:"passwordSecret,omitempty"`

	// Storage size
	StorageSize string `json:"storageSize,omitempty"`

	// Storage class
	StorageClass string `json:"storageClass,omitempty"`
}

// RedisConfig defines Redis settings
type RedisConfig struct {
	// Password (should be stored in secret)
	PasswordSecret string `json:"passwordSecret,omitempty"`

	// Memory limit
	MemoryLimit string `json:"memoryLimit,omitempty"`

	// Storage size for persistence
	StorageSize string `json:"storageSize,omitempty"`

	// Storage class
	StorageClass string `json:"storageClass,omitempty"`
}

// ElasticsearchConfig defines Elasticsearch settings
type ElasticsearchConfig struct {
	// Number of master nodes
	MasterNodes int32 `json:"masterNodes,omitempty"`

	// Number of data nodes
	DataNodes int32 `json:"dataNodes,omitempty"`

	// JVM heap size
	HeapSize string `json:"heapSize,omitempty"`

	// Storage size per node
	StorageSize string `json:"storageSize,omitempty"`

	// Storage class
	StorageClass string `json:"storageClass,omitempty"`

	// Index prefix
	IndexPrefix string `json:"indexPrefix,omitempty"`
}

// PrometheusConfig defines Prometheus settings
type PrometheusConfig struct {
	// Retention time
	Retention string `json:"retention,omitempty"`

	// Storage size
	StorageSize string `json:"storageSize,omitempty"`

	// Storage class
	StorageClass string `json:"storageClass,omitempty"`

	// Scrape interval
	ScrapeInterval string `json:"scrapeInterval,omitempty"`
}

// ApplicationConfig defines the KillKrill application settings
type ApplicationConfig struct {
	// Log receiver configuration
	LogReceiver ComponentConfig `json:"logReceiver"`

	// Metrics receiver configuration
	MetricsReceiver ComponentConfig `json:"metricsReceiver"`

	// Log worker configuration
	LogWorker ComponentConfig `json:"logWorker"`

	// Metrics worker configuration
	MetricsWorker ComponentConfig `json:"metricsWorker"`

	// Manager configuration
	Manager ComponentConfig `json:"manager"`

	// XDP filtering enabled
	XDPEnabled bool `json:"xdpEnabled,omitempty"`

	// Syslog port range
	SyslogPortRange string `json:"syslogPortRange,omitempty"`
}

// ComponentConfig defines configuration for a KillKrill component
type ComponentConfig struct {
	// Number of replicas
	Replicas int32 `json:"replicas,omitempty"`

	// Resource requirements
	Resources corev1.ResourceRequirements `json:"resources,omitempty"`

	// Image to use
	Image string `json:"image,omitempty"`

	// Image pull policy
	ImagePullPolicy corev1.PullPolicy `json:"imagePullPolicy,omitempty"`

	// Environment variables
	Env []corev1.EnvVar `json:"env,omitempty"`

	// Volume mounts
	VolumeMounts []corev1.VolumeMount `json:"volumeMounts,omitempty"`
}

// MonitoringConfig defines monitoring settings
type MonitoringConfig struct {
	// Enabled flag
	Enabled bool `json:"enabled,omitempty"`

	// AlertManager configuration
	AlertManager AlertManagerConfig `json:"alertManager,omitempty"`

	// ElastAlert configuration
	ElastAlert ElastAlertConfig `json:"elastAlert,omitempty"`
}

// AlertManagerConfig defines AlertManager settings
type AlertManagerConfig struct {
	// PagerDuty service key (should be stored in secret)
	PagerDutySecret string `json:"pagerDutySecret,omitempty"`

	// Slack webhook URL (should be stored in secret)
	SlackSecret string `json:"slackSecret,omitempty"`

	// SMTP configuration
	SMTP SMTPConfig `json:"smtp,omitempty"`
}

// SMTPConfig defines SMTP settings for email alerts
type SMTPConfig struct {
	// SMTP server
	Server string `json:"server,omitempty"`

	// SMTP port
	Port int32 `json:"port,omitempty"`

	// Username
	Username string `json:"username,omitempty"`

	// Password (should be stored in secret)
	PasswordSecret string `json:"passwordSecret,omitempty"`

	// From address
	From string `json:"from,omitempty"`
}

// ElastAlertConfig defines ElastAlert settings
type ElastAlertConfig struct {
	// Enabled flag
	Enabled bool `json:"enabled,omitempty"`

	// Rules configuration
	Rules []ElastAlertRule `json:"rules,omitempty"`
}

// ElastAlertRule defines an ElastAlert rule
type ElastAlertRule struct {
	// Rule name
	Name string `json:"name"`

	// Rule type
	Type string `json:"type"`

	// Index pattern
	Index string `json:"index"`

	// Filter conditions
	Filter map[string]interface{} `json:"filter,omitempty"`

	// Alert configuration
	Alert []string `json:"alert,omitempty"`
}

// StorageConfig defines storage settings
type StorageConfig struct {
	// Default storage class
	DefaultStorageClass string `json:"defaultStorageClass,omitempty"`

	// Backup configuration
	Backup BackupConfig `json:"backup,omitempty"`
}

// BackupConfig defines backup settings
type BackupConfig struct {
	// Enabled flag
	Enabled bool `json:"enabled,omitempty"`

	// Schedule (cron format)
	Schedule string `json:"schedule,omitempty"`

	// Retention days
	RetentionDays int32 `json:"retentionDays,omitempty"`

	// S3 configuration for backups
	S3 S3Config `json:"s3,omitempty"`
}

// S3Config defines S3 backup settings
type S3Config struct {
	// Bucket name
	Bucket string `json:"bucket,omitempty"`

	// Region
	Region string `json:"region,omitempty"`

	// Access key (should be stored in secret)
	AccessKeySecret string `json:"accessKeySecret,omitempty"`

	// Secret key (should be stored in secret)
	SecretKeySecret string `json:"secretKeySecret,omitempty"`
}

// SecurityConfig defines security settings
type SecurityConfig struct {
	// TLS configuration
	TLS TLSConfig `json:"tls,omitempty"`

	// Network policies enabled
	NetworkPolicies bool `json:"networkPolicies,omitempty"`

	// Pod security standards
	PodSecurity PodSecurityConfig `json:"podSecurity,omitempty"`
}

// TLSConfig defines TLS settings
type TLSConfig struct {
	// Enabled flag
	Enabled bool `json:"enabled,omitempty"`

	// Certificate issuer
	Issuer string `json:"issuer,omitempty"`

	// Certificate secret name
	CertSecret string `json:"certSecret,omitempty"`
}

// PodSecurityConfig defines pod security settings
type PodSecurityConfig struct {
	// Security context for non-privileged pods
	SecurityContext *corev1.SecurityContext `json:"securityContext,omitempty"`

	// Pod security context
	PodSecurityContext *corev1.PodSecurityContext `json:"podSecurityContext,omitempty"`
}

// KillKrillStatus defines the observed state of KillKrill
type KillKrillStatus struct {
	// INSERT ADDITIONAL STATUS FIELD - define observed state of cluster
	// Important: Run "make" to regenerate code after modifying this file

	// Conditions represent the latest available observations of an object's state
	Conditions []metav1.Condition `json:"conditions,omitempty"`

	// Phase represents the current phase of the KillKrill deployment
	Phase string `json:"phase,omitempty"`

	// ObservedGeneration is the last generation observed by the controller
	ObservedGeneration int64 `json:"observedGeneration,omitempty"`

	// ComponentStatus tracks the status of individual components
	ComponentStatus ComponentStatus `json:"componentStatus,omitempty"`

	// Endpoints exposes the service endpoints
	Endpoints EndpointsStatus `json:"endpoints,omitempty"`
}

// ComponentStatus tracks the status of KillKrill components
type ComponentStatus struct {
	// Log receiver status
	LogReceiver string `json:"logReceiver,omitempty"`

	// Metrics receiver status
	MetricsReceiver string `json:"metricsReceiver,omitempty"`

	// Log worker status
	LogWorker string `json:"logWorker,omitempty"`

	// Metrics worker status
	MetricsWorker string `json:"metricsWorker,omitempty"`

	// Manager status
	Manager string `json:"manager,omitempty"`

	// Infrastructure status
	Infrastructure InfrastructureStatus `json:"infrastructure,omitempty"`
}

// InfrastructureStatus tracks infrastructure component status
type InfrastructureStatus struct {
	// PostgreSQL status
	PostgreSQL string `json:"postgresql,omitempty"`

	// Redis status
	Redis string `json:"redis,omitempty"`

	// Elasticsearch status
	Elasticsearch string `json:"elasticsearch,omitempty"`

	// Prometheus status
	Prometheus string `json:"prometheus,omitempty"`

	// Grafana status
	Grafana string `json:"grafana,omitempty"`
}

// EndpointsStatus exposes service endpoints
type EndpointsStatus struct {
	// Manager UI URL
	ManagerURL string `json:"managerURL,omitempty"`

	// Grafana URL
	GrafanaURL string `json:"grafanaURL,omitempty"`

	// Kibana URL
	KibanaURL string `json:"kibanaURL,omitempty"`

	// Prometheus URL
	PrometheusURL string `json:"prometheusURL,omitempty"`

	// AlertManager URL
	AlertManagerURL string `json:"alertManagerURL,omitempty"`
}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status
//+kubebuilder:resource:scope=Namespaced
//+kubebuilder:printcolumn:name="Phase",type="string",JSONPath=".status.phase"
//+kubebuilder:printcolumn:name="Age",type="date",JSONPath=".metadata.creationTimestamp"

// KillKrill is the Schema for the killkrillcluster API
type KillKrill struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   KillKrillSpec   `json:"spec,omitempty"`
	Status KillKrillStatus `json:"status,omitempty"`
}

//+kubebuilder:object:root=true

// KillKrillList contains a list of KillKrill
type KillKrillList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []KillKrill `json:"items"`
}

func init() {
	SchemeBuilder.Register(&KillKrill{}, &KillKrillList{})
}
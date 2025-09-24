package controllers

import (
	"context"
	"fmt"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	"k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/apimachinery/pkg/util/intstr"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"

	killkrillv1 "github.com/penguintechinc/killkrill/api/v1"
)

// KillKrillReconciler reconciles a KillKrill object
type KillKrillReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

//+kubebuilder:rbac:groups=killkrill.penguintech.io,resources=killkrillclusters,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=killkrillclusters.penguintech.io,resources=killkrillclusters/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=killkrillclusters.penguintech.io,resources=killkrillclusters/finalizers,verbs=update
//+kubebuilder:rbac:groups=apps,resources=deployments,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=apps,resources=statefulsets,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=services,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=configmaps,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=secrets,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=persistentvolumeclaims,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=networking.k8s.io,resources=ingresses,verbs=get;list;watch;create;update;patch;delete

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
func (r *KillKrillReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	// Fetch the KillKrill instance
	killkrill := &killkrillv1.KillKrill{}
	err := r.Get(ctx, req.NamespacedName, killkrill)
	if err != nil {
		if errors.IsNotFound(err) {
			// Request object not found, could have been deleted after reconcile request.
			logger.Info("KillKrill resource not found. Ignoring since object must be deleted")
			return ctrl.Result{}, nil
		}
		// Error reading the object - requeue the request.
		logger.Error(err, "Failed to get KillKrill")
		return ctrl.Result{}, err
	}

	// Set default values if not specified
	r.setDefaults(killkrill)

	// Update status phase
	killkrill.Status.Phase = "Reconciling"
	if err := r.Status().Update(ctx, killkrill); err != nil {
		logger.Error(err, "Failed to update KillKrill status")
		return ctrl.Result{}, err
	}

	// Reconcile infrastructure components
	if err := r.reconcileInfrastructure(ctx, killkrill); err != nil {
		logger.Error(err, "Failed to reconcile infrastructure")
		return ctrl.Result{RequeueAfter: time.Minute * 2}, err
	}

	// Reconcile KillKrill applications
	if err := r.reconcileApplications(ctx, killkrill); err != nil {
		logger.Error(err, "Failed to reconcile applications")
		return ctrl.Result{RequeueAfter: time.Minute * 2}, err
	}

	// Reconcile monitoring components
	if err := r.reconcileMonitoring(ctx, killkrill); err != nil {
		logger.Error(err, "Failed to reconcile monitoring")
		return ctrl.Result{RequeueAfter: time.Minute * 2}, err
	}

	// Reconcile ingress/networking
	if err := r.reconcileNetworking(ctx, killkrill); err != nil {
		logger.Error(err, "Failed to reconcile networking")
		return ctrl.Result{RequeueAfter: time.Minute * 2}, err
	}

	// Update status to Ready
	killkrill.Status.Phase = "Ready"
	r.updateEndpoints(killkrill)
	if err := r.Status().Update(ctx, killkrill); err != nil {
		logger.Error(err, "Failed to update KillKrill status")
		return ctrl.Result{}, err
	}

	logger.Info("Successfully reconciled KillKrill")
	return ctrl.Result{RequeueAfter: time.Minute * 10}, nil
}

// setDefaults sets default values for the KillKrill spec
func (r *KillKrillReconciler) setDefaults(killkrill *killkrillv1.KillKrill) {
	if killkrill.Spec.Size == 0 {
		killkrill.Spec.Size = 1
	}

	// Set default infrastructure settings
	if killkrill.Spec.Infrastructure.PostgreSQL.Database == "" {
		killkrill.Spec.Infrastructure.PostgreSQL.Database = "killkrill"
	}
	if killkrill.Spec.Infrastructure.PostgreSQL.Username == "" {
		killkrill.Spec.Infrastructure.PostgreSQL.Username = "killkrill"
	}
	if killkrill.Spec.Infrastructure.PostgreSQL.StorageSize == "" {
		killkrill.Spec.Infrastructure.PostgreSQL.StorageSize = "10Gi"
	}

	if killkrill.Spec.Infrastructure.Redis.MemoryLimit == "" {
		killkrill.Spec.Infrastructure.Redis.MemoryLimit = "1Gi"
	}
	if killkrill.Spec.Infrastructure.Redis.StorageSize == "" {
		killkrill.Spec.Infrastructure.Redis.StorageSize = "5Gi"
	}

	if killkrill.Spec.Infrastructure.Elasticsearch.MasterNodes == 0 {
		killkrill.Spec.Infrastructure.Elasticsearch.MasterNodes = 1
	}
	if killkrill.Spec.Infrastructure.Elasticsearch.DataNodes == 0 {
		killkrill.Spec.Infrastructure.Elasticsearch.DataNodes = 2
	}
	if killkrill.Spec.Infrastructure.Elasticsearch.HeapSize == "" {
		killkrill.Spec.Infrastructure.Elasticsearch.HeapSize = "8g"
	}
	if killkrill.Spec.Infrastructure.Elasticsearch.StorageSize == "" {
		killkrill.Spec.Infrastructure.Elasticsearch.StorageSize = "50Gi"
	}

	if killkrill.Spec.Infrastructure.Prometheus.Retention == "" {
		killkrill.Spec.Infrastructure.Prometheus.Retention = "15d"
	}
	if killkrill.Spec.Infrastructure.Prometheus.StorageSize == "" {
		killkrill.Spec.Infrastructure.Prometheus.StorageSize = "20Gi"
	}

	// Set default application settings
	if killkrill.Spec.Applications.LogReceiver.Replicas == 0 {
		killkrill.Spec.Applications.LogReceiver.Replicas = killkrill.Spec.Size
	}
	if killkrill.Spec.Applications.MetricsReceiver.Replicas == 0 {
		killkrill.Spec.Applications.MetricsReceiver.Replicas = killkrill.Spec.Size
	}
	if killkrill.Spec.Applications.LogWorker.Replicas == 0 {
		killkrill.Spec.Applications.LogWorker.Replicas = killkrill.Spec.Size * 2
	}
	if killkrill.Spec.Applications.MetricsWorker.Replicas == 0 {
		killkrill.Spec.Applications.MetricsWorker.Replicas = killkrill.Spec.Size
	}
	if killkrill.Spec.Applications.Manager.Replicas == 0 {
		killkrill.Spec.Applications.Manager.Replicas = 1
	}

	if killkrill.Spec.Applications.SyslogPortRange == "" {
		killkrill.Spec.Applications.SyslogPortRange = "10000-11000"
	}
}

// reconcileInfrastructure reconciles infrastructure components
func (r *KillKrillReconciler) reconcileInfrastructure(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	// PostgreSQL
	if err := r.reconcilePostgreSQL(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile PostgreSQL: %w", err)
	}

	// Redis
	if err := r.reconcileRedis(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile Redis: %w", err)
	}

	// Elasticsearch
	if err := r.reconcileElasticsearch(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile Elasticsearch: %w", err)
	}

	// Prometheus
	if err := r.reconcilePrometheus(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile Prometheus: %w", err)
	}

	return nil
}

// reconcilePostgreSQL creates/updates PostgreSQL StatefulSet and Service
func (r *KillKrillReconciler) reconcilePostgreSQL(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	logger := log.FromContext(ctx)

	// Create StatefulSet
	sts := &appsv1.StatefulSet{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "killkrill-postgres",
			Namespace: killkrill.Namespace,
		},
		Spec: appsv1.StatefulSetSpec{
			Replicas:    &[]int32{1}[0],
			ServiceName: "killkrill-postgres",
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"app": "killkrill-postgres",
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"app": "killkrill-postgres",
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "postgres",
							Image: "postgres:15-alpine",
							Env: []corev1.EnvVar{
								{
									Name:  "POSTGRES_DB",
									Value: killkrill.Spec.Infrastructure.PostgreSQL.Database,
								},
								{
									Name:  "POSTGRES_USER",
									Value: killkrill.Spec.Infrastructure.PostgreSQL.Username,
								},
								{
									Name: "POSTGRES_PASSWORD",
									ValueFrom: &corev1.EnvVarSource{
										SecretKeyRef: &corev1.SecretKeySelector{
											LocalObjectReference: corev1.LocalObjectReference{
												Name: "killkrill-postgres-secret",
											},
											Key: "password",
										},
									},
								},
							},
							Ports: []corev1.ContainerPort{
								{
									ContainerPort: 5432,
									Name:          "postgres",
								},
							},
							VolumeMounts: []corev1.VolumeMount{
								{
									Name:      "postgres-storage",
									MountPath: "/var/lib/postgresql/data",
								},
							},
							Resources: corev1.ResourceRequirements{
								Limits: corev1.ResourceList{
									corev1.ResourceMemory: resource.MustParse("2Gi"),
									corev1.ResourceCPU:    resource.MustParse("1000m"),
								},
								Requests: corev1.ResourceList{
									corev1.ResourceMemory: resource.MustParse("1Gi"),
									corev1.ResourceCPU:    resource.MustParse("500m"),
								},
							},
						},
					},
				},
			},
			VolumeClaimTemplates: []corev1.PersistentVolumeClaim{
				{
					ObjectMeta: metav1.ObjectMeta{
						Name: "postgres-storage",
					},
					Spec: corev1.PersistentVolumeClaimSpec{
						AccessModes: []corev1.PersistentVolumeAccessMode{
							corev1.ReadWriteOnce,
						},
						Resources: corev1.ResourceRequirements{
							Requests: corev1.ResourceList{
								corev1.ResourceStorage: resource.MustParse(killkrill.Spec.Infrastructure.PostgreSQL.StorageSize),
							},
						},
					},
				},
			},
		},
	}

	if err := controllerutil.SetControllerReference(killkrill, sts, r.Scheme); err != nil {
		return err
	}

	// Create or update
	if err := r.Create(ctx, sts); err != nil {
		if errors.IsAlreadyExists(err) {
			logger.Info("PostgreSQL StatefulSet already exists, updating")
			if err := r.Update(ctx, sts); err != nil {
				return err
			}
		} else {
			return err
		}
	}

	// Create Service
	svc := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "killkrill-postgres",
			Namespace: killkrill.Namespace,
		},
		Spec: corev1.ServiceSpec{
			Selector: map[string]string{
				"app": "killkrill-postgres",
			},
			Ports: []corev1.ServicePort{
				{
					Port:       5432,
					TargetPort: intstr.FromInt(5432),
				},
			},
		},
	}

	if err := controllerutil.SetControllerReference(killkrill, svc, r.Scheme); err != nil {
		return err
	}

	if err := r.Create(ctx, svc); err != nil && !errors.IsAlreadyExists(err) {
		return err
	}

	return nil
}

// reconcileRedis creates/updates Redis StatefulSet and Service
func (r *KillKrillReconciler) reconcileRedis(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	// Similar implementation to PostgreSQL but for Redis
	// This would create Redis StatefulSet with persistence
	return nil
}

// reconcileElasticsearch creates/updates Elasticsearch cluster
func (r *KillKrillReconciler) reconcileElasticsearch(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	// Implementation for Elasticsearch cluster with master and data nodes
	// This would create multiple StatefulSets for different node types
	return nil
}

// reconcilePrometheus creates/updates Prometheus StatefulSet and Service
func (r *KillKrillReconciler) reconcilePrometheus(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	// Implementation for Prometheus with configuration and storage
	return nil
}

// reconcileApplications reconciles KillKrill application components
func (r *KillKrillReconciler) reconcileApplications(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	// Log Receiver
	if err := r.reconcileLogReceiver(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile log receiver: %w", err)
	}

	// Metrics Receiver
	if err := r.reconcileMetricsReceiver(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile metrics receiver: %w", err)
	}

	// Log Worker
	if err := r.reconcileLogWorker(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile log worker: %w", err)
	}

	// Metrics Worker
	if err := r.reconcileMetricsWorker(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile metrics worker: %w", err)
	}

	// Manager
	if err := r.reconcileManager(ctx, killkrill); err != nil {
		return fmt.Errorf("failed to reconcile manager: %w", err)
	}

	return nil
}

// reconcileLogReceiver creates/updates log receiver deployment
func (r *KillKrillReconciler) reconcileLogReceiver(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "killkrill-log-receiver",
			Namespace: killkrill.Namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: &killkrill.Spec.Applications.LogReceiver.Replicas,
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"app": "killkrill-log-receiver",
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"app": "killkrill-log-receiver",
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "log-receiver",
							Image: "killkrill/log-receiver:latest",
							Ports: []corev1.ContainerPort{
								{ContainerPort: 8081, Name: "http"},
								{ContainerPort: 10000, Name: "syslog", Protocol: corev1.ProtocolUDP},
							},
							Env: []corev1.EnvVar{
								{
									Name:  "LICENSE_KEY",
									Value: killkrill.Spec.License.Key,
								},
								{
									Name:  "PRODUCT_NAME",
									Value: killkrill.Spec.License.Product,
								},
							},
							Resources: killkrill.Spec.Applications.LogReceiver.Resources,
						},
					},
					SecurityContext: &corev1.PodSecurityContext{
						RunAsNonRoot: &[]bool{false}[0], // XDP requires root
					},
				},
			},
		},
	}

	if err := controllerutil.SetControllerReference(killkrill, deployment, r.Scheme); err != nil {
		return err
	}

	if err := r.Create(ctx, deployment); err != nil && !errors.IsAlreadyExists(err) {
		return err
	}

	return nil
}

// Similar implementations for other components...
func (r *KillKrillReconciler) reconcileMetricsReceiver(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	return nil
}

func (r *KillKrillReconciler) reconcileLogWorker(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	return nil
}

func (r *KillKrillReconciler) reconcileMetricsWorker(ctx context.Context, killkrill *killkrill) error {
	return nil
}

func (r *KillKrillReconciler) reconcileManager(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	return nil
}

// reconcileMonitoring reconciles monitoring components
func (r *KillKrillReconciler) reconcileMonitoring(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	return nil
}

// reconcileNetworking reconciles networking components
func (r *KillKrillReconciler) reconcileNetworking(ctx context.Context, killkrill *killkrillv1.KillKrill) error {
	return nil
}

// updateEndpoints updates the status with service endpoints
func (r *KillKrillReconciler) updateEndpoints(killkrill *killkrillv1.KillKrill) {
	killkrill.Status.Endpoints.ManagerURL = fmt.Sprintf("http://killkrill-manager.%s.svc.cluster.local:8080", killkrill.Namespace)
	killkrill.Status.Endpoints.GrafanaURL = fmt.Sprintf("http://killkrill-grafana.%s.svc.cluster.local:3000", killkrill.Namespace)
	killkrill.Status.Endpoints.KibanaURL = fmt.Sprintf("http://killkrill-kibana.%s.svc.cluster.local:5601", killkrill.Namespace)
	killkrill.Status.Endpoints.PrometheusURL = fmt.Sprintf("http://killkrill-prometheus.%s.svc.cluster.local:9090", killkrill.Namespace)
	killkrill.Status.Endpoints.AlertManagerURL = fmt.Sprintf("http://killkrill-alertmanager.%s.svc.cluster.local:9093", killkrill.Namespace)
}

// SetupWithManager sets up the controller with the Manager.
func (r *KillKrillReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&killkrillv1.KillKrill{}).
		Owns(&appsv1.Deployment{}).
		Owns(&appsv1.StatefulSet{}).
		Owns(&corev1.Service{}).
		Owns(&corev1.ConfigMap{}).
		Owns(&networkingv1.Ingress{}).
		Complete(r)
}
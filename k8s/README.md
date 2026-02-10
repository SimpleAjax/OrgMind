# OrgMind Kubernetes Deployment Guide

> Step-by-step guide for deploying OrgMind to Kubernetes

---

## Overview

OrgMind uses **Kustomize overlays** for environment-specific configurations:

```
k8s/
├── staging/          # Staging environment manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── api-deployment.yaml
│   ├── worker-deployment.yaml
│   ├── indexer-deployment.yaml
│   ├── ingress.yaml
│   ├── pvc.yaml
│   └── [stateful services...]
└── prod/             # Production environment manifests
    └── [same structure]
```

---

## Prerequisites

### 1. Tools Required

```bash
# kubectl (Kubernetes CLI)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/windows/amd64/kubectl.exe"

# Verify
kubectl version --client

# (Optional) k9s for cluster monitoring
choco install k9s
```

### 2. Kubernetes Cluster

**Options:**
- Local: **Minikube**, **Kind**, **Docker Desktop**
- Cloud: **GKE** (Google), **EKS** (AWS), **AKS** (Azure)
- Managed: **DigitalOcean Kubernetes**, **Linode LKE**

### 3. Container Registry Access

Ensure `ghcr.io/your-org/orgmind` is built and pushed:

```bash
# Build and push (done by CI/CD)
docker build -t ghcr.io/your-org/orgmind:latest -f docker/Dockerfile.api .
docker push ghcr.io/your-org/orgmind:latest
```

---

## Deployment Steps

### Step 1: Configure kubectl Context

```bash
# List available contexts
kubectl config get-contexts

# Switch to desired cluster
kubectl config use-context your-cluster-name

# Verify connection
kubectl cluster-info
```

### Step 2: Update Secrets

**IMPORTANT:** Update `k8s/staging/secret.yaml` with real values:

```bash
# Generate base64-encoded secrets
# Windows PowerShell:
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("your-secret-here"))

# Or use online tool: https://www.base64encode.org/
```

**Update these values:**
```yaml
# k8s/staging/secret.yaml
data:
  JWT_SECRET: <your-base64-jwt-secret>
  NEO4J_PASSWORD: <your-base64-neo4j-password>
  OPENAI_API_KEY: <your-base64-openai-key>
  MINIO_ACCESS_KEY: <your-base64-minio-access>
  MINIO_SECRET_KEY: <your-base64-minio-secret>
```

### Step 3: Update ConfigMap

Edit `k8s/staging/configmap.yaml`:

```yaml
# Update domain
CORS_ORIGINS: "https://your-staging-domain.com"
```

### Step 4: Update Ingress

Edit `k8s/staging/ingress.yaml`:

```yaml
# Update host
spec:
  rules:
  - host: api.your-staging-domain.com  # Change this
```

### Step 5: Deploy to Staging

```bash
# Apply all manifests
kubectl apply -f k8s/staging/

# Or apply in specific order:
kubectl apply -f k8s/staging/namespace.yaml
kubectl apply -f k8s/staging/configmap.yaml
kubectl apply -f k8s/staging/secret.yaml
kubectl apply -f k8s/staging/pvc.yaml

# Deploy stateful services (databases)
kubectl apply -f k8s/staging/redis.yaml
kubectl apply -f k8s/staging/neo4j.yaml
kubectl apply -f k8s/staging/qdrant.yaml
kubectl apply -f k8s/staging/meilisearch.yaml
kubectl apply -f k8s/staging/minio.yaml
kubectl apply -f k8s/staging/temporal.yaml

# Wait for databases to be ready
kubectl wait --for=condition=ready pod -l app=redis -n orgmind-staging --timeout=300s
kubectl wait --for=condition=ready pod -l app=neo4j -n orgmind-staging --timeout=300s

# Deploy application services
kubectl apply -f k8s/staging/api-deployment.yaml
kubectl apply -f k8s/staging/worker-deployment.yaml
kubectl apply -f k8s/staging/indexer-deployment.yaml

# Deploy ingress
kubectl apply -f k8s/staging/ingress.yaml
```

### Step 6: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n orgmind-staging

# Expected output:
# NAME                              READY   STATUS    RESTARTS
# orgmind-api-xxx                   1/1     Running   0
# orgmind-api-yyy                   1/1     Running   0
# orgmind-worker-xxx                1/1     Running   0
# orgmind-indexer-xxx               1/1     Running   0
# orgmind-redis-0                   1/1     Running   0
# orgmind-neo4j-0                   1/1     Running   0
# orgmind-qdrant-0                  1/1     Running   0
# orgmind-meilisearch-0             1/1     Running   0
# orgmind-minio-0                   1/1     Running   0
# orgmind-temporal-xxx              1/1     Running   0

# Check services
kubectl get svc -n orgmind-staging

# Check ingress
kubectl get ingress -n orgmind-staging
```

### Step 7: Access the Application

```bash
# Get ingress external IP
kubectl get ingress -n orgmind-staging

# Test health endpoint
curl https://api.your-staging-domain.com/health/ready

# Or port-forward for testing
kubectl port-forward svc/orgmind-api 8000:8000 -n orgmind-staging
curl http://localhost:8000/health/ready
```

---

## Production Deployment

### Differences from Staging

**Production changes (`k8s/prod/`):**

1. **Higher replica counts:**
   ```yaml
   # api-deployment.yaml
   spec:
     replicas: 5  # vs 2 in staging
   
   # HPA maxReplicas: 20  # vs 10 in staging
   ```

2. **Larger resource limits:**
   ```yaml
   resources:
     requests:
       cpu: 1000m      # vs 500m
       memory: 2Gi     # vs 1Gi
     limits:
       cpu: 4000m      # vs 2000m
       memory: 4Gi     # vs 2Gi
   ```

3. **Production TLS certificate:**
   ```yaml
   # ingress.yaml
   annotations:
     cert-manager.io/cluster-issuer: "letsencrypt-prod"  # vs letsencrypt-staging
   ```

4. **Multi-replica databases** (HA):
   ```yaml
   # neo4j.yaml
   spec:
     replicas: 3  # vs 1 in staging
   ```

### Deployment Command

```bash
# Production deployment (requires manual approval in CI/CD)
kubectl apply -f k8s/prod/
```

---

## Monitoring

### View Logs

```bash
# API logs
kubectl logs -f deployment/orgmind-api -n orgmind-staging

# Worker logs
kubectl logs -f deployment/orgmind-worker -n orgmind-staging

# All logs with label
kubectl logs -f -l app=orgmind -n orgmind-staging

# Tail last 100 lines
kubectl logs --tail=100 deployment/orgmind-api -n orgmind-staging
```

### Check Pod Status

```bash
# Detailed pod info
kubectl describe pod <pod-name> -n orgmind-staging

# Pod resource usage
kubectl top pods -n orgmind-staging

# Events
kubectl get events -n orgmind-staging --sort-by='.lastTimestamp'
```

### Access Services

```bash
# Port-forward to Neo4j browser
kubectl port-forward svc/orgmind-neo4j 7474:7474 -n orgmind-staging
# Open: http://localhost:7474

# Port-forward to MinIO console
kubectl port-forward svc/orgmind-minio 9001:9001 -n orgmind-staging
# Open: http://localhost:9001

# Port-forward to Temporal UI
kubectl port-forward svc/orgmind-temporal-ui 8080:8080 -n orgmind-staging
# Open: http://localhost:8080
```

---

## Scaling

### Manual Scaling

```bash
# Scale API pods
kubectl scale deployment orgmind-api --replicas=5 -n orgmind-staging

# Scale workers
kubectl scale deployment orgmind-worker --replicas=3 -n orgmind-staging
```

### Auto-scaling (HPA)

HPAs are already configured in deployment manifests:

```bash
# Check HPA status
kubectl get hpa -n orgmind-staging

# Describe HPA
kubectl describe hpa orgmind-api-hpa -n orgmind-staging
```

---

## Updates & Rollouts

### Update Image

```bash
# Update to new version
kubectl set image deployment/orgmind-api \
  api=ghcr.io/your-org/orgmind:v1.2.0 \
  -n orgmind-staging

# Check rollout status
kubectl rollout status deployment/orgmind-api -n orgmind-staging
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/orgmind-api -n orgmind-staging

# Rollback to specific revision
kubectl rollout undo deployment/orgmind-api --to-revision=2 -n orgmind-staging

# View rollout history
kubectl rollout history deployment/orgmind-api -n orgmind-staging
```

### Rolling Update Strategy

Already configured in deployments:

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # 1 extra pod during update
      maxUnavailable: 0  # No downtime
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n orgmind-staging

# If status is ImagePullBackOff
kubectl describe pod <pod-name> -n orgmind-staging
# Fix: Ensure image exists in registry

# If status is CrashLoopBackOff
kubectl logs <pod-name> -n orgmind-staging
# Fix: Check application logs for errors

# If status is Pending
kubectl describe pod <pod-name> -n orgmind-staging
# Fix: Check resource requests, PVC availability
```

### Database Connection Issues

```bash
# Test Redis connection
kubectl run -it --rm redis-test --image=redis:7-alpine --restart=Never -n orgmind-staging -- redis-cli -h orgmind-redis ping
# Should output: PONG

# Test Neo4j connection
kubectl run -it --rm neo4j-test --image=neo4j:5-community --restart=Never -n orgmind-staging -- \
  cypher-shell -a bolt://orgmind-neo4j:7687 -u neo4j -p orgmind_staging "RETURN 1"
```

### Persistent Volume Issues

```bash
# Check PVC status
kubectl get pvc -n orgmind-staging

# If status is Pending
kubectl describe pvc orgmind-data-pvc -n orgmind-staging
# Fix: Ensure StorageClass exists, check node capacity
```

### Ingress Not Working

```bash
# Check ingress status
kubectl get ingress -n orgmind-staging

# Describe ingress
kubectl describe ingress orgmind-ingress -n orgmind-staging

# Check ingress controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

---

## Cleanup

### Delete Staging Environment

```bash
# Delete all resources in namespace
kubectl delete namespace orgmind-staging

# Or delete specific resources
kubectl delete -f k8s/staging/
```

### Delete PVCs (CAUTION: Data Loss!)

```bash
# List PVCs
kubectl get pvc -n orgmind-staging

# Delete specific PVC
kubectl delete pvc orgmind-data-pvc -n orgmind-staging
```

---

## Cost Optimization

### Development/Testing

```bash
# Reduce replicas
kubectl scale deployment orgmind-api --replicas=1 -n orgmind-staging
kubectl scale deployment orgmind-worker --replicas=1 -n orgmind-staging
kubectl scale deployment orgmind-indexer --replicas=1 -n orgmind-staging

# Stop non-essential services
kubectl scale statefulset orgmind-meilisearch --replicas=0 -n orgmind-staging  # If not using search
```

### Production

- Use **node pools** with autoscaling
- Set appropriate **resource requests/limits**
- Use **cluster autoscaler** to scale nodes
- Consider **reserved instances** for stable workloads

---

## Security Checklist

- [ ] Update all secrets in `secret.yaml`
- [ ] Enable RBAC (Role-Based Access Control)
- [ ] Use NetworkPolicies to restrict pod communication
- [ ] Enable Pod Security Standards
- [ ] Use private container registry (or GHCR with authentication)
- [ ] Enable audit logging
- [ ] Regularly update base images
- [ ] Run security scans (Trivy, Snyk)

---

## Next Steps

1. **Set up monitoring:** Prometheus + Grafana
2. **Set up alerting:** PagerDuty, Slack integration
3. **Set up log aggregation:** ELK stack or Loki
4. **Configure backup:** Velero for cluster backups
5. **Set up CI/CD:** GitHub Actions integration

---

*Last Updated: 2026-02-10*

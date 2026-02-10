# =============================================================================
# Setup Local k3d Cluster for OrgMind
# Usage: .\setup-local.ps1
# =============================================================================

$CLUSTER_NAME = "orgmind-local"
$K3D_CONFIG = "k3d/config.yaml"
$IMAGE_TAG = "orgmind:local"

Write-Host "Setting up local k3d cluster for OrgMind..." -ForegroundColor Cyan

# ─── Helper: Fix kubeconfig for Windows ──────────────────────────────────────
function Fix-Kubeconfig {
    $kubeconfig = "$env:USERPROFILE\.kube\config"
    if (Test-Path $kubeconfig) {
        $content = Get-Content $kubeconfig -Raw
        if ($content -match 'host\.docker\.internal') {
            $content -replace 'host\.docker\.internal', '127.0.0.1' | Set-Content $kubeconfig
            Write-Host "  Fixed kubeconfig: host.docker.internal → 127.0.0.1" -ForegroundColor Cyan
        }
    }
}

# ─── Step 1: Check/Create Cluster ────────────────────────────────────────────
$clusterExists = k3d cluster list -o json 2>$null | ConvertFrom-Json | Where-Object { $_.name -eq $CLUSTER_NAME }
if ($clusterExists) {
    Write-Host "Cluster '$CLUSTER_NAME' already exists." -ForegroundColor Yellow
    $response = Read-Host "Delete and recreate? (y/N)"
    if ($response -eq "y") {
        Write-Host "Deleting cluster..."
        k3d cluster delete $CLUSTER_NAME
    } else {
        Write-Host "Using existing cluster."
        Fix-Kubeconfig
    }
}

if (-not (k3d cluster list -o json 2>$null | ConvertFrom-Json | Where-Object { $_.name -eq $CLUSTER_NAME })) {
    Write-Host "Creating cluster '$CLUSTER_NAME'..." -ForegroundColor Green
    k3d cluster create --config $K3D_CONFIG
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create cluster." -ForegroundColor Red
        exit 1
    }
    Fix-Kubeconfig
}

# Verify connectivity
Write-Host "Verifying cluster connectivity..." -ForegroundColor Cyan
kubectl cluster-info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Cannot connect to cluster. Attempting kubeconfig fix..." -ForegroundColor Yellow
    Fix-Kubeconfig
    kubectl cluster-info
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Still cannot connect. Please check Docker Desktop is running." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  Cluster is reachable." -ForegroundColor Green

# ─── Step 2: Install NGINX Ingress Controller ────────────────────────────────
Write-Host "Installing NGINX Ingress Controller..." -ForegroundColor Green
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml 2>&1 | Out-Null
Write-Host "  Waiting for Ingress Controller pods..."
kubectl wait --namespace ingress-nginx `
    --for=condition=ready pod `
    --selector=app.kubernetes.io/component=controller `
    --timeout=120s

# ─── Step 3: Build Docker Image ──────────────────────────────────────────────
Write-Host "Building Docker image '$IMAGE_TAG'..." -ForegroundColor Green
docker build -t $IMAGE_TAG -f docker/Dockerfile.api .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Image built successfully." -ForegroundColor Green

# ─── Step 4: Import Image into k3d ───────────────────────────────────────────
Write-Host "Importing image into k3d cluster..." -ForegroundColor Green
k3d image import $IMAGE_TAG -c $CLUSTER_NAME
if ($LASTEXITCODE -ne 0) {
    Write-Host "Image import failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Image imported." -ForegroundColor Green

# ─── Step 5: Deploy with Kustomize ───────────────────────────────────────────
Write-Host "Creating namespace..." -ForegroundColor Green
kubectl create namespace orgmind-local --dry-run=client -o yaml | kubectl apply -f -

Write-Host "Deploying application stack (k8s/local)..." -ForegroundColor Green
kubectl apply -k k8s/local
if ($LASTEXITCODE -ne 0) {
    Write-Host "Deployment failed. Run 'kubectl apply -k k8s/local' manually to see errors." -ForegroundColor Red
    exit 1
}

# ─── Step 6: Wait for Rollout ────────────────────────────────────────────────
Write-Host "Waiting for pods to become ready..." -ForegroundColor Cyan
kubectl rollout status deployment/orgmind-api -n orgmind-local --timeout=180s

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host " OrgMind Local Environment Ready!" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  API:              http://localhost:8080/health/ready" -ForegroundColor White
Write-Host "  API Docs:         http://localhost:8080/docs" -ForegroundColor White
Write-Host "  Neo4j Browser:    http://localhost:7474" -ForegroundColor White
Write-Host "  MinIO Console:    http://localhost:9001" -ForegroundColor White
Write-Host ""
Write-Host "  Useful commands:" -ForegroundColor Yellow
Write-Host "    kubectl get pods -n orgmind-local" -ForegroundColor Gray
Write-Host "    kubectl logs -f deploy/orgmind-api -n orgmind-local" -ForegroundColor Gray
Write-Host ""
Write-Host "  To redeploy after code changes:" -ForegroundColor Yellow
Write-Host "    docker build -t $IMAGE_TAG -f docker/Dockerfile.api ." -ForegroundColor Gray
Write-Host "    k3d image import $IMAGE_TAG -c $CLUSTER_NAME" -ForegroundColor Gray
Write-Host "    kubectl rollout restart deploy/orgmind-api -n orgmind-local" -ForegroundColor Gray
Write-Host ""

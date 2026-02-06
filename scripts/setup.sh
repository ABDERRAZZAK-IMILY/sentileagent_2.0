#!/bin/bash
# ============================================
# SentinelAgent Setup Script
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command_exists docker; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command_exists docker-compose; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Create environment file
setup_environment() {
    log_info "Setting up environment..."
    
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log_warning "Created .env file from .env.example"
            log_warning "Please edit .env file with your configuration"
        else
            log_error ".env.example file not found"
            exit 1
        fi
    else
        log_info ".env file already exists"
    fi
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p data/mongodb
    mkdir -p data/qdrant
    mkdir -p data/redis
    mkdir -p data/iris
    mkdir -p logs
    
    log_success "Directories created"
}

# Pull Docker images
pull_images() {
    log_info "Pulling Docker images..."
    docker-compose pull
    log_success "Docker images pulled"
}

# Start infrastructure services
start_infrastructure() {
    log_info "Starting infrastructure services..."
    
    docker-compose up -d zookeeper kafka mongodb qdrant redis
    
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Check services health
    services=("zookeeper" "kafka" "mongodb" "qdrant" "redis")
    for service in "${services[@]}"; do
        if docker-compose ps | grep -q "$service.*Up"; then
            log_success "$service is running"
        else
            log_error "$service failed to start"
            docker-compose logs "$service"
            exit 1
        fi
    done
}

# Start application services
start_application() {
    log_info "Starting application services..."
    
    docker-compose up -d backend iris-service
    
    log_info "Waiting for backend to be ready..."
    sleep 30
    
    # Check backend health
    max_attempts=30
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8080/actuator/health | grep -q '"status":"UP"'; then
            log_success "Backend is healthy"
            break
        fi
        log_info "Waiting for backend... (attempt $attempt/$max_attempts)"
        sleep 10
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "Backend failed to start"
        docker-compose logs backend
        exit 1
    fi
    
    # Start frontend
    docker-compose up -d frontend
    log_success "Application services started"
}

# Start monitoring
start_monitoring() {
    log_info "Starting monitoring services..."
    
    docker-compose up -d prometheus grafana
    
    log_info "Waiting for Grafana to be ready..."
    sleep 10
    
    log_success "Monitoring services started"
    log_info "Grafana available at: http://localhost:3000"
    log_info "Prometheus available at: http://localhost:9090"
}

# Display access information
show_access_info() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "                    🛡️ SentinelAgent Setup Complete"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  📊 Dashboard:     http://localhost:4200"
    echo "  🔧 API:           http://localhost:8080"
    echo "  📈 Grafana:       http://localhost:3000 (admin/admin)"
    echo "  🔍 Prometheus:    http://localhost:9090"
    echo ""
    echo "  Default Login:"
    echo "    Username: admin"
    echo "    Password: admin123"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "Useful commands:"
    echo "  View logs:        docker-compose logs -f [service]"
    echo "  Stop services:    docker-compose down"
    echo "  Restart service:  docker-compose restart [service]"
    echo ""
}

# Main setup function
main() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "              🛡️ SentinelAgent Setup Script"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    check_prerequisites
    setup_environment
    create_directories
    pull_images
    start_infrastructure
    start_application
    start_monitoring
    show_access_info
    
    log_success "Setup completed successfully!"
}

# Run main function
main "$@"

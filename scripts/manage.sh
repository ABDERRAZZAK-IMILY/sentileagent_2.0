#!/bin/bash
# ============================================
# SentinelAgent Management Script
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

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

# Show help
show_help() {
    cat << EOF
SentinelAgent Management Script

Usage: $0 [command] [options]

Commands:
    start           Start all services
    stop            Stop all services
    restart         Restart all services
    status          Show service status
    logs [service]  View logs (optionally for specific service)
    update          Update all services to latest version
    backup          Backup database and configuration
    restore [file]  Restore from backup
    reset           Reset all data (WARNING: Destructive!)
    clean           Clean up Docker resources
    test            Run health checks
    shell [service] Open shell in service container
    
Services:
    backend, frontend, iris-service, mongodb, kafka, qdrant, redis,
    prometheus, grafana, zookeeper

Examples:
    $0 start                    # Start all services
    $0 logs backend             # View backend logs
    $0 shell mongodb            # Open MongoDB shell
    $0 backup                   # Create backup
    $0 restore backup-xxx.tar   # Restore from backup

EOF
}

# Start services
start_services() {
    log_info "Starting SentinelAgent services..."
    docker-compose up -d
    log_success "Services started"
    
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # Check health
    check_health
}

# Stop services
stop_services() {
    log_info "Stopping SentinelAgent services..."
    docker-compose down
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting SentinelAgent services..."
    docker-compose restart
    log_success "Services restarted"
}

# Show status
show_status() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "                    Service Status"
    echo "═══════════════════════════════════════════════════════════════"
    docker-compose ps
    echo ""
    
    # Check disk usage
    echo "Disk Usage:"
    docker system df
}

# View logs
view_logs() {
    local service="$1"
    if [ -n "$service" ]; then
        log_info "Viewing logs for $service..."
        docker-compose logs -f "$service"
    else
        log_info "Viewing logs for all services..."
        docker-compose logs -f
    fi
}

# Update services
update_services() {
    log_info "Updating SentinelAgent services..."
    
    # Pull latest images
    docker-compose pull
    
    # Rebuild local images
    docker-compose build --no-cache
    
    # Restart services
    docker-compose up -d
    
    log_success "Services updated"
}

# Backup data
backup_data() {
    local backup_dir="backups"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="sentinel-backup-$timestamp.tar.gz"
    
    mkdir -p "$backup_dir"
    
    log_info "Creating backup: $backup_file"
    
    # Backup MongoDB
    log_info "Backing up MongoDB..."
    docker-compose exec -T mongodb mongodump --archive --db=sentinelagent > "$backup_dir/mongodb-$timestamp.archive"
    
    # Backup configuration
    log_info "Backing up configuration..."
    cp .env "$backup_dir/env-$timestamp" 2>/dev/null || true
    
    # Create tar archive
    tar -czf "$backup_dir/$backup_file" -C "$backup_dir" "mongodb-$timestamp.archive" "env-$timestamp" 2>/dev/null
    
    # Cleanup temporary files
    rm -f "$backup_dir/mongodb-$timestamp.archive" "$backup_dir/env-$timestamp"
    
    log_success "Backup created: $backup_dir/$backup_file"
}

# Restore data
restore_data() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Please specify backup file"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    log_warning "This will overwrite existing data. Are you sure? (y/N)"
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_info "Restore cancelled"
        exit 0
    fi
    
    log_info "Restoring from: $backup_file"
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Restore MongoDB
    log_info "Restoring MongoDB..."
    docker-compose exec -T mongodb mongorestore --archive --drop < "$temp_dir"/*.archive
    
    # Cleanup
    rm -rf "$temp_dir"
    
    log_success "Restore completed"
}

# Reset all data
reset_data() {
    log_warning "WARNING: This will delete ALL data!"
    log_warning "Are you sure? Type 'DELETE' to confirm:"
    read -r confirm
    
    if [ "$confirm" != "DELETE" ]; then
        log_info "Reset cancelled"
        exit 0
    fi
    
    log_info "Stopping services..."
    docker-compose down -v
    
    log_info "Removing data volumes..."
    docker volume prune -f
    
    log_info "Removing local data..."
    rm -rf data/
    
    log_success "All data has been reset"
    log_info "Run '$0 start' to start fresh"
}

# Clean up Docker resources
cleanup() {
    log_info "Cleaning up Docker resources..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes
    docker volume prune -f
    
    # Remove unused networks
    docker network prune -f
    
    log_success "Cleanup completed"
}

# Health check
check_health() {
    log_info "Running health checks..."
    
    local failed=0
    
    # Check backend
    if curl -s http://localhost:8080/actuator/health | grep -q '"status":"UP"'; then
        log_success "Backend: Healthy"
    else
        log_error "Backend: Unhealthy"
        failed=1
    fi
    
    # Check MongoDB
    if docker-compose exec -T mongodb mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
        log_success "MongoDB: Healthy"
    else
        log_error "MongoDB: Unhealthy"
        failed=1
    fi
    
    # Check Kafka
    if docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:29092 >/dev/null 2>&1; then
        log_success "Kafka: Healthy"
    else
        log_error "Kafka: Unhealthy"
        failed=1
    fi
    
    # Check Redis
    if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        log_success "Redis: Healthy"
    else
        log_error "Redis: Unhealthy"
        failed=1
    fi
    
    if [ $failed -eq 0 ]; then
        log_success "All health checks passed"
    else
        log_error "Some health checks failed"
        exit 1
    fi
}

# Open shell in container
open_shell() {
    local service="$1"
    
    if [ -z "$service" ]; then
        log_error "Please specify a service"
        exit 1
    fi
    
    log_info "Opening shell in $service..."
    docker-compose exec "$service" /bin/sh
}

# Main function
main() {
    case "${1:-}" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            view_logs "$2"
            ;;
        update)
            update_services
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data "$2"
            ;;
        reset)
            reset_data
            ;;
        clean)
            cleanup
            ;;
        test)
            check_health
            ;;
        shell)
            open_shell "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: ${1:-}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"

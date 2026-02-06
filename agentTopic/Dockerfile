# ============================================
# SentinelAgent Go Agent - Docker Build
# ============================================

FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git gcc musl-dev

WORKDIR /app

# Copy go.mod and go.sum first for better layer caching
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY *.go ./

# Build the application
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o sentinel-agent .

# Runtime stage
FROM alpine:latest

# Install runtime dependencies for system metrics collection
RUN apk add --no-cache ca-certificates

# Create non-root user (note: some metrics require privileged mode)
RUN addgroup -S sentinel && adduser -S sentinel -G sentinel

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/sentinel-agent .

# Copy default config
COPY agent_config.json .

# Create directory for logs
RUN mkdir -p /app/logs && chown -R sentinel:sentinel /app

# Note: The agent needs privileged mode to collect system metrics
# This is configured in docker-compose.yml

# Environment variables
ENV AGENT_CONFIG_PATH=/app/agent_config.json
ENV AGENT_LOG_PATH=/app/logs/sentinelagent.log

# Run as root for system metrics collection (required for /proc access)
# In production, use appropriate capabilities instead
USER root

# Run the agent
CMD ["./sentinel-agent"]

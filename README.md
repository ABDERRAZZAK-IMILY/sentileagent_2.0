# 🛡️ SentinelAgent

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.5.7-brightgreen?logo=spring)](https://spring.io)
[![Angular](https://img.shields.io/badge/Angular-17-red?logo=angular)](https://angular.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> An enterprise-grade SOC-oriented cybersecurity platform that correlates telemetry (network/host signals) with AI-assisted analysis to surface suspicious activity and generate actionable security reports.

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Monitoring](#-monitoring)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## ✨ Features

### Core Capabilities

- 🔐 **Multi-Factor Authentication** - Password-based and iris biometric authentication
- 📊 **Real-time Telemetry** - System metrics collection via Go agents
- 🤖 **AI-Powered Analysis** - Spring AI integration for threat detection and enrichment
- 🚨 **Intelligent Alerting** - Rule-based and ML-based threat detection
- 📈 **SOC Dashboard** - Real-time visualization of security metrics
- 🔍 **Threat Intelligence** - RAG (Retrieval Augmented Generation) for security insights
- 📝 **Audit Logging** - Complete activity tracking for compliance

### Security Features

- JWT-based authentication with configurable expiration
- Role-based access control (RBAC)
- Iris biometric authentication via Python service
- Encrypted API communications (TLS support)
- Secure credential management

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SentinelAgent Platform                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐           │
│  │   Frontend   │────▶│   Backend    │◀────│   Agents     │           │
│  │  (Angular)   │     │  (Spring Boot│     │    (Go)      │           │
│  └──────────────┘     └──────┬───────┘     └──────────────┘           │
│         │                    │                                         │
│         │            ┌───────┴───────┐                                │
│         │            │               │                                │
│         ▼            ▼               ▼                                │
│  ┌──────────────┐  ┌────────┐   ┌──────────┐                         │
│  │Iris Service  │  │ Kafka  │   │ MongoDB  │                         │
│  │  (Python)    │  │        │   │          │                         │
│  └──────────────┘  └────────┘   └──────────┘                         │
│                         │               │                             │
│                         ▼               ▼                             │
│                   ┌────────┐      ┌──────────┐                       │
│                   │Qdrant  │      │  Redis   │                       │
│                   │(Vector)│      │ (Cache)  │                       │
│                   └────────┘      └──────────┘                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Details

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | Angular 17+ | SOC Dashboard UI |
| **Backend** | Spring Boot 3.5+ | REST API, Business Logic |
| **Agent** | Go 1.21+ | System telemetry collection |
| **Iris Service** | Python 3.11 + OpenCV | Biometric authentication |
| **AI/ML** | Python + Jupyter | Threat detection models |
| **Message Queue** | Apache Kafka | Event streaming |
| **Database** | MongoDB | Primary data storage |
| **Vector DB** | Qdrant | AI embeddings storage |
| **Cache** | Redis | Session and data caching |
| **Monitoring** | Prometheus + Grafana | Metrics and alerting |

## 🚀 Quick Start

### Prerequisites

- Docker 24.0+ and Docker Compose 2.20+
- 8GB+ RAM available
- OpenAI API key (for AI features)

### 1. Clone the Repository

```bash
git clone https://github.com/ABDERRAZZAK-IMILY/SentinelAgent.git
cd SentinelAgent
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
nano .env
```

### 3. Start All Services

```bash
docker-compose up -d
```

### 4. Access the Application

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend Dashboard | http://localhost:4200 | admin / admin123 |
| Backend API | http://localhost:8080 | - |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | - |

### 5. Verify Installation

```bash
# Check all services are running
docker-compose ps

# View logs
docker-compose logs -f backend

# Test API health
curl http://localhost:8080/actuator/health
```

## 📦 Installation

### Production Deployment

#### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml sentinelagent

# Verify services
docker stack ps sentinelagent
```

#### Using Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/mongodb.yaml
kubectl apply -f k8s/kafka.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml

# Verify deployment
kubectl get pods -n sentinelagent
```

### Manual Installation

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for detailed manual setup instructions.

## ⚙️ Configuration

### Backend Configuration

Create `backend/src/main/resources/application-local.yml`:

```yaml
spring:
  data:
    mongodb:
      uri: mongodb://localhost:27017/sentinelagent
  kafka:
    bootstrap-servers: localhost:9092
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
    qdrant:
      host: localhost
      port: 6334

jwt:
  secret: ${JWT_SECRET}
  expiration: 86400000

logging:
  level:
    com.sentinelagent: DEBUG
```

### Agent Configuration

Edit `agentTopic/agent_config.json`:

```json
{
  "serverUrl": "http://localhost:8080",
  "kafkaBroker": "localhost:9092",
  "kafkaTopic": "telemetry",
  "collection": {
    "metricsIntervalSeconds": 10,
    "heartbeatIntervalSeconds": 30,
    "processesLimit": 50
  }
}
```

### Iris Service Configuration

Environment variables:

```bash
export THRESHOLD=0.85
export FEATURES_FILE=/app/data/stored_features.npy
export SPRING_BOOT_URL=http://backend:8080
```

## 📚 API Documentation

### REST API Endpoints

#### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | User login |
| POST | `/api/v1/auth/refresh` | Refresh token |
| POST | `/api/v1/auth/logout` | User logout |

#### Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/agents/register` | Register new agent |
| GET | `/api/v1/agents` | List all agents |
| GET | `/api/v1/agents/{id}` | Get agent details |
| POST | `/api/v1/agents/{id}/heartbeat` | Agent heartbeat |
| DELETE | `/api/v1/agents/{id}` | Unregister agent |

#### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/alerts` | List alerts |
| GET | `/api/v1/alerts/{id}` | Get alert details |
| PUT | `/api/v1/alerts/{id}/status` | Update alert status |
| POST | `/api/v1/alerts/acknowledge` | Acknowledge alerts |

#### Telemetry

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/telemetry` | Submit telemetry |
| GET | `/api/v1/telemetry/{agentId}` | Get agent telemetry |
| GET | `/api/v1/telemetry/metrics` | Get aggregated metrics |

### WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `/ws/alerts` | Real-time alert stream |
| `/ws/metrics` | Real-time metrics stream |

### OpenAPI/Swagger

Access the interactive API documentation at:
- http://localhost:8080/swagger-ui.html
- http://localhost:8080/v3/api-docs

## 📊 Monitoring

### Grafana Dashboards

Pre-configured dashboards include:

1. **SOC Overview** - System health, alerts, and metrics
2. **Agent Status** - Agent connectivity and performance
3. **Security Metrics** - Threat detection and response times
4. **Infrastructure** - CPU, memory, and disk usage

### Prometheus Metrics

Key metrics exposed:

```
# Application metrics
http_server_requests_seconds_count
http_server_requests_seconds_sum
jvm_memory_used_bytes
jvm_memory_max_bytes
system_cpu_usage

# Custom metrics
sentinel_agent_last_heartbeat_seconds
sentinel_alerts_total
sentinel_telemetry_received_total
```

### Alerting

Configure alerts in `monitoring/prometheus/alert_rules.yml`:

```yaml
- alert: HighCPUUsage
  expr: system_cpu_usage > 0.8
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High CPU usage detected"
```

## 💻 Development

### Backend Development

```bash
cd backend

# Run with Maven
./mvnw spring-boot:run -Dspring-boot.run.profiles=local

# Run tests
./mvnw test

# Build
./mvnw clean package -DskipTests
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
ng serve

# Build for production
ng build --configuration production

# Run tests
ng test
```

### Agent Development

```bash
cd agentTopic

# Build
go build -o sentinel-agent .

# Run
./sentinel-agent

# Test
go test -v ./...
```

### Iris Service Development

```bash
cd iris_service

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python app.py

# Test
pytest tests/
```

## 🔧 Troubleshooting

### Common Issues

#### Backend fails to connect to MongoDB

```bash
# Check MongoDB is running
docker-compose ps mongodb

# Check connection
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# View logs
docker-compose logs mongodb
```

#### Kafka connection issues

```bash
# Verify Kafka is healthy
docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:29092

# List topics
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:29092
```

#### Agent registration fails

```bash
# Check backend is accessible
curl http://localhost:8080/actuator/health

# Verify agent config
cat agentTopic/agent_config.json

# Run agent with verbose logging
./sentinel-agent -v
```

### Debug Mode

Enable debug logging:

```bash
# Backend
LOGGING_LEVEL=DEBUG docker-compose up backend

# Agent
export LOG_LEVEL=debug
./sentinel-agent
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Spring Boot](https://spring.io/projects/spring-boot)
- [Angular](https://angular.io)
- [Apache Kafka](https://kafka.apache.org)
- [MongoDB](https://www.mongodb.com)
- [Qdrant](https://qdrant.tech)
- [Prometheus](https://prometheus.io)
- [Grafana](https://grafana.com)

## 📞 Support

- 📧 Email: azeimily2001@gmail.com
- 🐛 Issues: [GitHub Issues](https://github.com/ABDERRAZZAK-IMILY/SentinelAgent/issues)

---

<p align="center">
  Made with ❤️ by the SentinelAgent Team
</p>

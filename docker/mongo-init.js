// ============================================
// SentinelAgent MongoDB Initialization Script
// ============================================

db = db.getSiblingDB('sentinelagent');

// Create collections
db.createCollection('agents');
db.createCollection('alerts');
db.createCollection('telemetry');
db.createCollection('users');
db.createCollection('threats');
db.createCollection('audit_logs');

// Create indexes for agents collection
db.agents.createIndex({ "agentId": 1 }, { unique: true });
db.agents.createIndex({ "hostname": 1 });
db.agents.createIndex({ "status": 1 });
db.agents.createIndex({ "lastHeartbeat": 1 });
db.agents.createIndex({ "apiKey": 1 }, { unique: true, sparse: true });

// Create indexes for alerts collection
db.alerts.createIndex({ "alertId": 1 }, { unique: true });
db.alerts.createIndex({ "agentId": 1 });
db.alerts.createIndex({ "severity": 1 });
db.alerts.createIndex({ "status": 1 });
db.alerts.createIndex({ "timestamp": -1 });
db.alerts.createIndex({ "threatType": 1 });
db.alerts.createIndex({ "severity": 1, "timestamp": -1 });

// Create indexes for telemetry collection
db.telemetry.createIndex({ "agentId": 1 });
db.telemetry.createIndex({ "timestamp": -1 });
db.telemetry.createIndex({ "agentId": 1, "timestamp": -1 });
db.telemetry.createIndex({ "cpuUsage": 1 });
db.telemetry.createIndex({ "ramUsedPercent": 1 });

// Create TTL index for old telemetry data (90 days)
db.telemetry.createIndex(
  { "timestamp": 1 },
  { expireAfterSeconds: 7776000 }
);

// Create indexes for users collection
db.users.createIndex({ "username": 1 }, { unique: true });
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "role": 1 });

// Create indexes for threats collection
db.threats.createIndex({ "threatId": 1 }, { unique: true });
db.threats.createIndex({ "signature": 1 });
db.threats.createIndex({ "severity": 1 });

// Create indexes for audit logs
db.audit_logs.createIndex({ "timestamp": -1 });
db.audit_logs.createIndex({ "userId": 1 });
db.audit_logs.createIndex({ "action": 1 });

// TTL index for audit logs (1 year)
db.audit_logs.createIndex(
  { "timestamp": 1 },
  { expireAfterSeconds: 31536000 }
);

// Create default admin user (password should be changed after first login)
// Password: admin123 (bcrypt hashed)
db.users.insertOne({
  "username": "admin",
  "email": "admin@sentinelagent.local",
  "password": "$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy",
  "role": "ADMIN",
  "firstName": "System",
  "lastName": "Administrator",
  "isActive": true,
  "mfaEnabled": false,
  "createdAt": new Date(),
  "updatedAt": new Date(),
  "lastLogin": null
});

print('SentinelAgent database initialized successfully');

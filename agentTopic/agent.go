// ============================================
// SentinelAgent - Secure Network Intelligence Module
// Go Agent for System Telemetry Collection
// ============================================

package main

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"sort"
	"syscall"
	"time"

	"github.com/IBM/sarama"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
	gnet "github.com/shirou/gopsutil/v3/net"
	"github.com/shirou/gopsutil/v3/process"
)

// ==================================================================
// Configuration Types
// ==================================================================

type AgentConfig struct {
	ServerURL   string `json:"serverUrl"`
	AgentID     string `json:"agentId"`
	ApiKey      string `json:"apiKey"`
	KafkaBroker string `json:"kafkaBroker"`
	KafkaTopic  string `json:"kafkaTopic"`
	Collection  struct {
		MetricsIntervalSeconds    int  `json:"metricsIntervalSeconds"`
		HeartbeatIntervalSeconds  int  `json:"heartbeatIntervalSeconds"`
		ProcessesLimit            int  `json:"processesLimit"`
		NetworkConnectionsLimit   int  `json:"networkConnectionsLimit"`
		EnableNetworkSpeed        bool `json:"enableNetworkSpeed"`
		EnableDetailedProcesses   bool `json:"enableDetailedProcesses"`
	} `json:"collection"`
	Security struct {
		TLSEnabled      bool   `json:"tlsEnabled"`
		TLSSkipVerify   bool   `json:"tlsSkipVerify"`
		CertPath        string `json:"certPath"`
		KeyPath         string `json:"keyPath"`
	} `json:"security"`
	Logging struct {
		Level       string `json:"level"`
		FilePath    string `json:"filePath"`
		MaxSizeMB   int    `json:"maxSizeMB"`
		MaxBackups  int    `json:"maxBackups"`
		MaxAgeDays  int    `json:"maxAgeDays"`
	} `json:"logging"`
}

const (
	ConfigFile = "agent_config.json"
	Version    = "1.1.0"
)

var config AgentConfig
var logger *log.Logger

// ==================================================================
// Data Models
// ==================================================================

type MetricReport struct {
	AgentID        string              `json:"agentId"`
	ApiKey         string              `json:"apiKey"`
	Hostname       string              `json:"hostname"`
	OsVersion      string              `json:"osVersion"`
	AgentVersion   string              `json:"agentVersion"`
	CpuUsage       float64             `json:"cpuUsage"`
	RamUsedPercent float64             `json:"ramUsedPercent"`
	RamTotalMb     uint64              `json:"ramTotalMb"`
	RamUsedMb      uint64              `json:"ramUsedMb"`
	DiskUsedPercent float64            `json:"diskUsedPercent"`
	DiskTotalGb    uint64              `json:"diskTotalGb"`
	DiskUsedGb     uint64              `json:"diskUsedGb"`
	Processes      []ProcessModel      `json:"processes"`
	NetworkConnections []NetworkConnection `json:"networkConnections"`
	BytesSentSec   uint64              `json:"bytesSentSec"`
	BytesRecvSec   uint64              `json:"bytesRecvSec"`
	Timestamp      time.Time           `json:"timestamp"`
	UptimeSeconds  uint64              `json:"uptimeSeconds"`
}

type ProcessModel struct {
	Pid       int32   `json:"pid"`
	Name      string  `json:"name"`
	Cpu       float64 `json:"cpu"`
	MemPercent float32 `json:"memPercent"`
	Username  string  `json:"username"`
	Status    string  `json:"status"`
}

type NetworkConnection struct {
	Pid           int32  `json:"pid"`
	LocalAddress  string `json:"localAddress"`
	LocalPort     uint32 `json:"localPort"`
	RemoteAddress string `json:"remoteAddress"`
	RemotePort    uint32 `json:"remotePort"`
	ProcessName   string `json:"processName"`
	Status        string `json:"status"`
	Protocol      string `json:"protocol"`
}

type RegistrationRequest struct {
	Hostname        string `json:"hostname"`
	OperatingSystem string `json:"operatingSystem"`
	AgentVersion    string `json:"agentVersion"`
	IpAddress       string `json:"ipAddress"`
	MacAddress      string `json:"macAddress"`
}

type RegistrationResponse struct {
	AgentID string `json:"agentId"`
	ApiKey  string `json:"apiKey"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type HeartbeatRequest struct {
	AgentID        string  `json:"agentId"`
	CpuUsage       float64 `json:"cpuUsage"`
	RamUsedPercent float64 `json:"ramUsedPercent"`
	Status         string  `json:"status"`
	Timestamp      string  `json:"timestamp"`
}

// ==================================================================
// Network Stats Tracking
// ==================================================================

var lastBytesSent uint64
var lastBytesRecv uint64
var lastCheckTime time.Time

func initNetworkStats() {
	lastCheckTime = time.Now()
	io, err := gnet.IOCounters(false)
	if err == nil && len(io) > 0 {
		lastBytesSent = io[0].BytesSent
		lastBytesRecv = io[0].BytesRecv
	}
}

func calculateNetworkSpeed() (sentSec, recvSec uint64) {
	now := time.Now()
	elapsed := now.Sub(lastCheckTime).Seconds()
	
	if elapsed <= 0 {
		return 0, 0
	}
	
	io, err := gnet.IOCounters(false)
	if err != nil || len(io) == 0 {
		return 0, 0
	}
	
	sentDiff := io[0].BytesSent - lastBytesSent
	recvDiff := io[0].BytesRecv - lastBytesRecv
	
	sentSec = uint64(float64(sentDiff) / elapsed)
	recvSec = uint64(float64(recvDiff) / elapsed)
	
	lastBytesSent = io[0].BytesSent
	lastBytesRecv = io[0].BytesRecv
	lastCheckTime = now
	
	return sentSec, recvSec
}

// ==================================================================
// Configuration Management
// ==================================================================

func loadDefaultConfig() {
	config.ServerURL = "http://localhost:8080"
	config.KafkaBroker = "localhost:9092"
	config.KafkaTopic = "telemetry"
	config.Collection.MetricsIntervalSeconds = 10
	config.Collection.HeartbeatIntervalSeconds = 30
	config.Collection.ProcessesLimit = 50
	config.Collection.NetworkConnectionsLimit = 100
	config.Collection.EnableNetworkSpeed = true
	config.Collection.EnableDetailedProcesses = true
	config.Logging.Level = "info"
	config.Logging.FilePath = "sentinelagent.log"
}

func loadConfig() bool {
	data, err := os.ReadFile(ConfigFile)
	if err != nil {
		logger.Printf("Config file not found: %v", err)
		return false
	}
	
	if err := json.Unmarshal(data, &config); err != nil {
		logger.Printf("Error parsing config: %v", err)
		return false
	}
	
	// Override with environment variables if set
	if serverURL := os.Getenv("SERVER_URL"); serverURL != "" {
		config.ServerURL = serverURL
	}
	if kafkaBroker := os.Getenv("KAFKA_BROKER"); kafkaBroker != "" {
		config.KafkaBroker = kafkaBroker
	}
	if kafkaTopic := os.Getenv("KAFKA_TOPIC"); kafkaTopic != "" {
		config.KafkaTopic = kafkaTopic
	}
	if agentID := os.Getenv("AGENT_ID"); agentID != "" {
		config.AgentID = agentID
	}
	if apiKey := os.Getenv("API_KEY"); apiKey != "" {
		config.ApiKey = apiKey
	}
	
	return true
}

func saveConfig() error {
	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(ConfigFile, data, 0644)
}

// ==================================================================
// System Information Collection
// ==================================================================

func getHostname() string {
	hostname, _ := os.Hostname()
	return hostname
}

func getOSVersion() string {
	info, err := host.Info()
	if err != nil {
		return runtime.GOOS + " " + runtime.GOARCH
	}
	return fmt.Sprintf("%s %s (%s)", info.Platform, info.PlatformVersion, info.KernelVersion)
}

func getIPAddress() string {
	addrs, err := gnet.InterfaceAddrs()
	if err != nil {
		return "unknown"
	}
	
	for _, addr := range addrs {
		if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
			if ipnet.IP.To4() != nil {
				return ipnet.IP.String()
			}
		}
	}
	return "unknown"
}

func getMacAddress() string {
	interfaces, err := gnet.Interfaces()
	if err != nil {
		return "unknown"
	}
	
	for _, iface := range interfaces {
		if len(iface.HardwareAddr) > 0 && iface.Flags&net.FlagUp != 0 {
			return iface.HardwareAddr
		}
	}
	return "unknown"
}

func getUptime() uint64 {
	info, err := host.Info()
	if err != nil {
		return 0
	}
	return info.Uptime
}

// ==================================================================
// Metrics Collection
// ==================================================================

func collectMetrics() (*MetricReport, error) {
	// CPU Usage
	cpuPercent, err := cpu.Percent(0, false)
	if err != nil {
		return nil, fmt.Errorf("failed to get CPU usage: %w", err)
	}
	
	// Memory Usage
	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return nil, fmt.Errorf("failed to get memory info: %w", err)
	}
	
	// Disk Usage
	diskInfo, err := disk.Usage("/")
	if err != nil {
		return nil, fmt.Errorf("failed to get disk info: %w", err)
	}
	
	report := &MetricReport{
		AgentID:         config.AgentID,
		ApiKey:          config.ApiKey,
		Hostname:        getHostname(),
		OsVersion:       getOSVersion(),
		AgentVersion:    Version,
		CpuUsage:        cpuPercent[0],
		RamUsedPercent:  memInfo.UsedPercent,
		RamTotalMb:      memInfo.Total / 1024 / 1024,
		RamUsedMb:       memInfo.Used / 1024 / 1024,
		DiskUsedPercent: diskInfo.UsedPercent,
		DiskTotalGb:     diskInfo.Total / 1024 / 1024 / 1024,
		DiskUsedGb:      diskInfo.Used / 1024 / 1024 / 1024,
		Timestamp:       time.Now().UTC(),
		UptimeSeconds:   getUptime(),
	}
	
	// Network Speed
	if config.Collection.EnableNetworkSpeed {
		report.BytesSentSec, report.BytesRecvSec = calculateNetworkSpeed()
	}
	
	// Process Information
	if config.Collection.EnableDetailedProcesses {
		report.Processes = collectProcesses()
	}
	
	// Network Connections
	report.NetworkConnections = collectNetworkConnections()
	
	return report, nil
}

func collectProcesses() []ProcessModel {
	processes, err := process.Processes()
	if err != nil {
		return nil
	}
	
	var processList []ProcessModel
	
	for _, p := range processes {
		// Get process info
		name, _ := p.Name()
		cpu, _ := p.CPUPercent()
		mem, _ := p.MemoryPercent()
		username, _ := p.Username()
		status, _ := p.Status()
		
		processList = append(processList, ProcessModel{
			Pid:        p.Pid,
			Name:       name,
			Cpu:        cpu,
			MemPercent: mem,
			Username:   username,
			Status:     status[0],
		})
		
		if len(processList) >= config.Collection.ProcessesLimit {
			break
		}
	}
	
	// Sort by CPU usage
	sort.Slice(processList, func(i, j int) bool {
		return processList[i].Cpu > processList[j].Cpu
	})
	
	return processList
}

func collectNetworkConnections() []NetworkConnection {
	connections, err := gnet.Connections("all")
	if err != nil {
		return nil
	}
	
	var connList []NetworkConnection
	
	for _, conn := range connections {
		// Get process name if available
		processName := "unknown"
		if conn.Pid > 0 {
			if p, err := process.NewProcess(conn.Pid); err == nil {
				processName, _ = p.Name()
			}
		}
		
		connList = append(connList, NetworkConnection{
			Pid:           conn.Pid,
			LocalAddress:  conn.Laddr.IP,
			LocalPort:     conn.Laddr.Port,
			RemoteAddress: conn.Raddr.IP,
			RemotePort:    conn.Raddr.Port,
			ProcessName:   processName,
			Status:        conn.Status,
			Protocol:      conn.Type,
		})
		
		if len(connList) >= config.Collection.NetworkConnectionsLimit {
			break
		}
	}
	
	return connList
}

// ==================================================================
// Registration & Communication
// ==================================================================

func registerAgent() error {
	reqBody := RegistrationRequest{
		Hostname:        getHostname(),
		OperatingSystem: getOSVersion(),
		AgentVersion:    Version,
		IpAddress:       getIPAddress(),
		MacAddress:      getMacAddress(),
	}
	
	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return err
	}
	
	url := fmt.Sprintf("%s/api/v1/agents/register", config.ServerURL)
	
	client := &http.Client{Timeout: 30 * time.Second}
	if config.Security.TLSEnabled && config.Security.TLSSkipVerify {
		client.Transport = &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		}
	}
	
	resp, err := client.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("registration failed: %s - %s", resp.Status, string(body))
	}
	
	var regResp RegistrationResponse
	if err := json.NewDecoder(resp.Body).Decode(&regResp); err != nil {
		return err
	}
	
	config.AgentID = regResp.AgentID
	config.ApiKey = regResp.ApiKey
	
	if err := saveConfig(); err != nil {
		logger.Printf("Warning: Failed to save config: %v", err)
	}
	
	logger.Printf("Agent registered successfully: %s", config.AgentID)
	return nil
}

func sendHeartbeat() error {
	metrics, err := collectMetrics()
	if err != nil {
		return err
	}
	
	heartbeat := HeartbeatRequest{
		AgentID:        config.AgentID,
		CpuUsage:       metrics.CpuUsage,
		RamUsedPercent: metrics.RamUsedPercent,
		Status:         "ACTIVE",
		Timestamp:      time.Now().UTC().Format(time.RFC3339),
	}
	
	jsonData, _ := json.Marshal(heartbeat)
	url := fmt.Sprintf("%s/api/v1/agents/%s/heartbeat", config.ServerURL, config.AgentID)
	
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("heartbeat failed: %s", resp.Status)
	}
	
	return nil
}

func sendToKafka(report *MetricReport) error {
	config := sarama.NewConfig()
	config.Producer.RequiredAcks = sarama.WaitForLocal
	config.Producer.Retry.Max = 3
	config.Producer.Return.Successes = true
	
	producer, err := sarama.NewSyncProducer([]string{config.KafkaBroker}, config)
	if err != nil {
		return fmt.Errorf("failed to create producer: %w", err)
	}
	defer producer.Close()
	
	jsonData, err := json.Marshal(report)
	if err != nil {
		return err
	}
	
	msg := &sarama.ProducerMessage{
		Topic: config.KafkaTopic,
		Key:   sarama.StringEncoder(report.AgentID),
		Value: sarama.ByteEncoder(jsonData),
	}
	
	_, _, err = producer.SendMessage(msg)
	return err
}

// ==================================================================
// Main Application
// ==================================================================

func main() {
	// Initialize logger
	logFile, err := os.OpenFile("sentinelagent.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		log.Fatal(err)
	}
	defer logFile.Close()
	
	logger = log.New(io.MultiWriter(os.Stdout, logFile), "[SentinelAgent] ", log.LstdFlags)
	
	logger.Println("═══════════════════════════════════════════════════")
	logger.Println("  🛡️  SentinelAgent Secure Intelligence Module")
	logger.Printf("  Version: %s", Version)
	logger.Println("═══════════════════════════════════════════════════")
	
	// Load configuration
	loadDefaultConfig()
	if !loadConfig() {
		logger.Println("📝 No existing configuration found. Will attempt registration.")
	}
	
	// Initialize network stats
	initNetworkStats()
	
	// Register if needed
	if config.AgentID == "" {
		logger.Println("🔐 Registering agent with server...")
		if err := registerAgent(); err != nil {
			logger.Printf("⚠️ Registration failed: %v", err)
			logger.Println("📡 Continuing in standalone mode (Kafka only)")
		}
	}
	
	// Setup signal handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	
	// Create ticker for metrics collection
	metricsTicker := time.NewTicker(time.Duration(config.Collection.MetricsIntervalSeconds) * time.Second)
	defer metricsTicker.Stop()
	
	heartbeatTicker := time.NewTicker(time.Duration(config.Collection.HeartbeatIntervalSeconds) * time.Second)
	defer heartbeatTicker.Stop()
	
	logger.Println("✅ Agent started successfully")
	logger.Printf("📊 Metrics interval: %ds", config.Collection.MetricsIntervalSeconds)
	logger.Printf("💓 Heartbeat interval: %ds", config.Collection.HeartbeatIntervalSeconds)
	
	// Main loop
	for {
		select {
		case <-metricsTicker.C:
			report, err := collectMetrics()
			if err != nil {
				logger.Printf("❌ Error collecting metrics: %v", err)
				continue
			}
			
			// Send to Kafka
			if err := sendToKafka(report); err != nil {
				logger.Printf("⚠️ Failed to send to Kafka: %v", err)
			} else {
				logger.Printf("📤 Metrics sent | CPU: %.1f%% | RAM: %.1f%% | Net: ↑%d ↓%d bytes/s",
					report.CpuUsage, report.RamUsedPercent, report.BytesSentSec, report.BytesRecvSec)
			}
			
		case <-heartbeatTicker.C:
			if config.AgentID != "" {
				if err := sendHeartbeat(); err != nil {
					logger.Printf("⚠️ Heartbeat failed: %v", err)
				}
			}
			
		case sig := <-sigChan:
			logger.Printf("\n🛑 Received signal: %v", sig)
			logger.Println("👋 Shutting down gracefully...")
			return
		}
	}
}

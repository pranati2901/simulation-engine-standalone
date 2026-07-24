# GoalCert — Install Wazuh Agent on Windows VM
# Run this on DC01 and WS01 after Wazuh Manager is up
#
# Usage (as Administrator):
#   .\install-wazuh-agent.ps1 -WazuhServer "192.168.56.30"
#
# The agent will register with the Wazuh Manager and start
# forwarding Sysmon + Security event logs.

param(
    [string]$WazuhServer = "192.168.56.30",
    [string]$AgentGroup = "goalcert-lab"
)

$ErrorActionPreference = "Stop"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  GoalCert — Wazuh Agent Installer" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Download Wazuh Agent MSI
$msiUrl = "https://packages.wazuh.com/4.x/windows/wazuh-agent-4.9.0-1.msi"
$msiPath = "$env:TEMP\wazuh-agent.msi"

Write-Host "[1/4] Downloading Wazuh Agent..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $msiUrl -OutFile $msiPath

# Install with manager IP
Write-Host "[2/4] Installing Wazuh Agent (Manager: $WazuhServer)..." -ForegroundColor Yellow
msiexec.exe /i $msiPath /q `
    WAZUH_MANAGER="$WazuhServer" `
    WAZUH_AGENT_GROUP="$AgentGroup" `
    WAZUH_REGISTRATION_SERVER="$WazuhServer"

Start-Sleep -Seconds 5

# Start the agent service
Write-Host "[3/4] Starting Wazuh Agent service..." -ForegroundColor Yellow
NET START WazuhSvc

# Verify
Write-Host "[4/4] Verifying agent status..." -ForegroundColor Yellow
$status = Get-Service WazuhSvc -ErrorAction SilentlyContinue
if ($status.Status -eq "Running") {
    Write-Host ""
    Write-Host "  Wazuh Agent is RUNNING" -ForegroundColor Green
    Write-Host "  Manager: $WazuhServer" -ForegroundColor Green
    Write-Host "  Agent logs: C:\Program Files (x86)\ossec-agent\ossec.log" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "  WARNING: Agent service not running" -ForegroundColor Red
    Write-Host "  Check: C:\Program Files (x86)\ossec-agent\ossec.log" -ForegroundColor Red
}

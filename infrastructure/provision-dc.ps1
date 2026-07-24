# GoalCert live-fire — Domain Controller provisioning (Phase 2).
#
# Run this ONCE, as Administrator, INSIDE the Windows Server DC after the domain is up
# (works for any DC: Vagrant, VirtualBox/VMware manual, or cloud). It makes the box ready for
# GoalCert's real AD attacks AND the real event-log detection:
#
#   1. WinRM listener        — so GoalCert can read the DC's event log for detection
#   2. Sysmon                — telemetry for lateral-movement detection
#   3. Audit policy          — so DCSync (4662), Kerberos (4769) and Logon (4624) events fire
#   4. Attack account        — added to Domain Admins (DCSync needs replication rights)
#   5. Kerberoastable SPN     — a service account so cred.kerberoast has something to roast
#
# Usage (elevated PowerShell on the DC):
#   .\provision-dc.ps1 -AttackUser vagrant
#
param(
    [string]$AttackUser = "vagrant",
    [string]$ServiceAccountPassword = "P@ssw0rd!"
)
$ErrorActionPreference = "Continue"
function Step($n, $m) { Write-Host "`n[$n] $m" -ForegroundColor Cyan }

Step 1 "Enabling WinRM (so GoalCert can query the event log for detection)..."
winrm quickconfig -quiet
Enable-PSRemoting -Force -SkipNetworkProfileCheck
netsh advfirewall firewall add rule name="GoalCert-WinRM" dir=in action=allow protocol=TCP localport=5985 | Out-Null
Write-Host "  WinRM listening on 5985" -ForegroundColor Green

Step 2 "Installing Sysmon (endpoint telemetry)..."
if (-not (Get-Service Sysmon64 -ErrorAction SilentlyContinue)) {
    Invoke-WebRequest "https://download.sysinternals.com/files/Sysmon.zip" -OutFile C:\sysmon.zip
    Expand-Archive C:\sysmon.zip -DestinationPath C:\Sysmon -Force
    Invoke-WebRequest "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/master/sysmonconfig-export.xml" -OutFile C:\Sysmon\config.xml
    C:\Sysmon\Sysmon64.exe -accepteula -i C:\Sysmon\config.xml
    Write-Host "  Sysmon installed" -ForegroundColor Green
} else { Write-Host "  Sysmon already present" -ForegroundColor Green }

Step 3 "Enabling audit policy (DCSync / Kerberos / Logon events)..."
auditpol /set /subcategory:"Directory Service Access" /success:enable /failure:enable | Out-Null
auditpol /set /subcategory:"Kerberos Service Ticket Operations" /success:enable /failure:enable | Out-Null
auditpol /set /subcategory:"Logon" /success:enable /failure:enable | Out-Null
Write-Host "  Audit policy set" -ForegroundColor Green

Step 4 "Granting the attack account ($AttackUser) Domain Admin (DCSync needs replication rights)..."
Import-Module ActiveDirectory -ErrorAction SilentlyContinue
Add-ADGroupMember -Identity "Domain Admins" -Members $AttackUser -ErrorAction SilentlyContinue
Write-Host "  $AttackUser is now a Domain Admin (demo lab only!)" -ForegroundColor Green

Step 5 "Creating a kerberoastable service account (svc_sql)..."
if (-not (Get-ADUser -Filter "SamAccountName -eq 'svc_sql'" -ErrorAction SilentlyContinue)) {
    $pw = ConvertTo-SecureString $ServiceAccountPassword -AsPlainText -Force
    New-ADUser -Name "svc_sql" -SamAccountName "svc_sql" -AccountPassword $pw -Enabled $true -PasswordNeverExpires $true
    Set-ADUser -Identity "svc_sql" -ServicePrincipalNames @{Add="MSSQLSvc/sql01.goalcert.local:1433"}
    Write-Host "  svc_sql created with SPN" -ForegroundColor Green
} else { Write-Host "  svc_sql already exists" -ForegroundColor Green }

Write-Host "`nDC is ready for GoalCert live-fire (Phase 2)." -ForegroundColor Green
Write-Host "  Point GoalCert at this DC with:  GOALCERT_LAB_BACKEND=windows_ad  GOALCERT_AD_DC_HOST=<this DC IP>"

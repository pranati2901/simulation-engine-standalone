# GoalCert live-fire — host-side pre-flight check for the Windows-AD lab (Phase 2).
# Verifies the attacker host can (a) reach the DC, (b) has Impacket, (c) can query the DC over WinRM.
#
#   pwsh infrastructure/lab-ad-check.ps1 -DcHost 192.168.56.10 -User vagrant -Password vagrant
#
param(
    [string]$DcHost = "192.168.56.10",
    [string]$User = "vagrant",
    [string]$Password = "vagrant",
    [string]$Domain = "GOALCERT"
)
function Ok($m){ Write-Host "  [OK]  $m" -ForegroundColor Green }
function Bad($m){ Write-Host "  [!!]  $m" -ForegroundColor Red }

Write-Host "GoalCert AD lab pre-flight ($DcHost)" -ForegroundColor Cyan

Write-Host "`n1. Network reachability"
if (Test-Connection -ComputerName $DcHost -Count 1 -Quiet) { Ok "DC responds to ping" } else { Bad "DC not pinging (VM up? host-only network?)" }

Write-Host "`n2. WinRM (5985) — needed for detection"
if ((Test-NetConnection $DcHost -Port 5985 -WarningAction SilentlyContinue).TcpTestSucceeded) { Ok "WinRM port 5985 open" } else { Bad "5985 closed (run provision-dc.ps1 on the DC)" }

Write-Host "`n3. Attacker tooling on this host"
$impacket = Get-Command impacket-secretsdump -ErrorAction SilentlyContinue
if ($impacket) { Ok "impacket-secretsdump found" } else { Bad "impacket missing -> pip install impacket" }
$py = (python -c "import winrm" 2>&1)
if ($LASTEXITCODE -eq 0) { Ok "pywinrm installed" } else { Bad "pywinrm missing -> pip install pywinrm" }

Write-Host "`n4. Live SMB check against the DC (NetExec or Impacket)"
$nxc = Get-Command nxc -ErrorAction SilentlyContinue
if ($nxc) { nxc smb $DcHost -u $User -p $Password 2>&1 | Select-Object -First 3 }
elseif ($impacket) { Write-Host "  (run: impacket-secretsdump -just-dc $Domain/$User`:$Password@$DcHost  to test DCSync)" }

Write-Host "`nIf all green: set GOALCERT_LAB_BACKEND=windows_ad and arm Live-fire in a session." -ForegroundColor Cyan

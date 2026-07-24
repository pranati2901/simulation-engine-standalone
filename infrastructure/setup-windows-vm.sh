#!/bin/bash
# GoalCert — Create Windows 11 ARM VM in UTM
# Usage: ./setup-windows-vm.sh /path/to/windows11.iso
#
# This creates a VM with:
#   - 4GB RAM, 2 CPUs, 64GB disk
#   - Named "GoalCert-DC01"
#   - Ready for Sysmon + Wazuh Agent + Atomic Red Team

set -e

ISO_PATH="${1:-$(ls -t ~/Downloads/Win11*.iso 2>/dev/null | head -1)}"

if [ -z "$ISO_PATH" ] || [ ! -f "$ISO_PATH" ]; then
    echo "ERROR: Windows 11 ARM ISO not found."
    echo "Usage: ./setup-windows-vm.sh /path/to/Win11_*.iso"
    echo ""
    echo "Download from: https://www.microsoft.com/en-us/software-download/windows11arm64"
    exit 1
fi

echo "Found ISO: $ISO_PATH"
echo "Size: $(du -h "$ISO_PATH" | cut -f1)"
echo ""
echo "=== Creating GoalCert-DC01 VM ==="
echo "  RAM: 4096 MB"
echo "  CPUs: 2"
echo "  Disk: 64 GB"
echo "  ISO: $ISO_PATH"
echo ""

# Check UTM is running
if ! pgrep -x "UTM" > /dev/null; then
    echo "Starting UTM..."
    open -a UTM
    sleep 3
fi

echo ""
echo "============================================"
echo "UTM does not support fully automated VM creation via CLI."
echo "Follow these steps in UTM:"
echo ""
echo "1. Click '+' (Create a New Virtual Machine)"
echo "2. Select 'Virtualize'"
echo "3. Select 'Windows'"
echo "4. Check 'Install Windows 10 or higher'"
echo "5. Check 'Import VHDX Image' → UNCHECK this"
echo "6. Click 'Browse' → select: $ISO_PATH"
echo "7. Set Memory: 4096 MB"
echo "8. Set CPU Cores: 2"
echo "9. Set Storage: 64 GB"
echo "10. Skip Shared Directory"
echo "11. Name: GoalCert-DC01"
echo "12. Click 'Save'"
echo "13. Click the Play button to start the VM"
echo ""
echo "During Windows Setup:"
echo "  - Click 'I don't have a product key'"
echo "  - Select 'Windows 11 Pro' (has RDP + Group Policy)"
echo "  - Accept license, Custom install, Next"
echo "  - Set username: Administrator"
echo "  - Set password: GoalCert2026!"
echo ""
echo "After Windows installs, run setup-post-install.ps1"
echo "inside the VM to install Sysmon + WinRM + Atomic Red Team."
echo "============================================"

#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Bootstrap-Skript für WinRM-Konfiguration auf Windows Server

.DESCRIPTION
    Dieses Skript muss LOKAL auf dem Windows Server ausgeführt werden.
    Es konfiguriert WinRM für HTTPS-Verbindungen mit Ansible.

.EXAMPLE
    .\bootstrap_winrm.ps1
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step {
    param([string]$Step, [string]$Message)
    Write-Host "[$Step] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# Schritt 1: WinRM Service überprüfen
Write-Step "1/7" "WinRM-Service überprüfen..."
try {
    $winrmService = Get-Service -Name WinRM
    if ($winrmService.Status -ne "Running") {
        Start-Service WinRM
        Set-Service WinRM -StartupType Automatic
    }
    Write-Success "WinRM-Service läuft"
} catch {
    Write-Err "WinRM-Service konnte nicht gestartet werden: $_"
}

# Schritt 2: WinRM QuickConfig
Write-Step "2/7" "WinRM QuickConfig ausführen..."
try {
    winrm quickconfig -force -quiet 2>$null
    Write-Success "WinRM QuickConfig abgeschlossen"
} catch {
    Write-Err "WinRM QuickConfig fehlgeschlagen: $_"
}

# Schritt 3: Selbstsigniertes Zertifikat erstellen
Write-Step "3/7" "SSL-Zertifikat erstellen..."
try {
    $hostname = $env:COMPUTERNAME
    $cert = New-SelfSignedCertificate `
        -DnsName $hostname `
        -CertStoreLocation "Cert:\LocalMachine\My" `
        -NotAfter (Get-Date).AddYears(5) `
        -KeySpec KeyExchange `
        -KeyExportPolicy Exportable
    $thumbprint = $cert.Thumbprint
    Write-Success "Zertifikat erstellt (Thumbprint: $thumbprint)"
} catch {
    Write-Err "Zertifikat-Erstellung fehlgeschlagen: $_"
}

# Schritt 4: HTTPS-Listener konfigurieren
Write-Step "4/7" "HTTPS-Listener konfigurieren..."
try {
    winrm delete winrm/config/Listener?Address=*+Transport=HTTPS 2>$null
    $listenerConfig = "@{Hostname=`"$hostname`";CertificateThumbprint=`"$thumbprint`"}"
    winrm create "winrm/config/Listener?Address=*+Transport=HTTPS" $listenerConfig
    Write-Success "HTTPS-Listener konfiguriert auf Port 5986"
} catch {
    Write-Err "HTTPS-Listener konnte nicht erstellt werden: $_"
}

# Schritt 5: Firewall-Regel erstellen
Write-Step "5/7" "Firewall-Regel für WinRM HTTPS erstellen..."
try {
    $existingRule = Get-NetFirewallRule -DisplayName "WinRM HTTPS" -ErrorAction SilentlyContinue
    if (-not $existingRule) {
        New-NetFirewallRule `
            -DisplayName "WinRM HTTPS" `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort 5986 `
            -Action Allow `
            -Profile Any | Out-Null
    }
    Write-Success "Firewall-Regel für Port 5986 erstellt"
} catch {
    Write-Err "Firewall-Regel konnte nicht erstellt werden: $_"
}

# Schritt 6: WinRM-Konfiguration optimieren
Write-Step "6/7" "WinRM-Konfiguration optimieren..."
try {
    winrm set winrm/config/service/auth '@{Basic="true"}'
    winrm set winrm/config/service/auth '@{Negotiate="true"}'
    winrm set winrm/config/service '@{AllowUnencrypted="false"}'
    winrm set winrm/config/winrs '@{MaxMemoryPerShellMB="1024"}'
    winrm set winrm/config/winrs '@{IdleTimeout="7200000"}'
    winrm set winrm/config '@{MaxTimeoutms="7200000"}'
    winrm set winrm/config/client '@{TrustedHosts="*"}'
    Write-Success "WinRM-Konfiguration optimiert"
} catch {
    Write-Err "WinRM-Konfiguration fehlgeschlagen: $_"
}

# Schritt 7: WinRM Service neu starten
Write-Step "7/7" "WinRM-Service neu starten..."
try {
    Restart-Service WinRM -Force
    Start-Sleep -Seconds 5
    Write-Success "WinRM-Service neu gestartet"
} catch {
    Write-Err "WinRM-Service konnte nicht neu gestartet werden: $_"
}

# Zusammenfassung
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  WinRM-Konfiguration erfolgreich!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Verbindungsinformationen:" -ForegroundColor Cyan
Write-Host "  Host: $hostname"
Write-Host "  Port: 5986 (HTTPS)"
Write-Host "  Transport: HTTPS"
Write-Host "  Auth: Basic/Negotiate"
Write-Host ""
Write-Host "Nächste Schritte:" -ForegroundColor Yellow
Write-Host "  1. Trage die IP-Adresse in inventory.ini ein"
Write-Host "  2. Führe 'ansible-playbook site.yml' aus"
Write-Host ""
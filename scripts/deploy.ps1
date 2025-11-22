# PowerShell Deployment Script for Kite Auto Trading (Windows)
# Run this script with Administrator privileges

param(
    [string]$InstallPath = "C:\KiteAutoTrading",
    [string]$ConfigType = "conservative"
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Kite Auto Trading - Windows Deployment" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check for Administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script requires Administrator privileges" -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again" -ForegroundColor Yellow
    exit 1
}

# Step 1: Create application directories
Write-Host "Step 1: Creating application directories..." -ForegroundColor Green
$LogDir = Join-Path $InstallPath "logs"
$DataDir = Join-Path $InstallPath "data"
$ConfigDir = Join-Path $InstallPath "config"

New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

# Step 2: Check Python installation
Write-Host "Step 2: Checking Python installation..." -ForegroundColor Green
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org/" -ForegroundColor Yellow
    exit 1
}

# Step 3: Create virtual environment
Write-Host "Step 3: Creating Python virtual environment..." -ForegroundColor Green
$VenvPath = Join-Path $InstallPath "venv"
python -m venv $VenvPath

# Step 4: Activate virtual environment and install dependencies
Write-Host "Step 4: Installing Python dependencies..." -ForegroundColor Green
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
& $ActivateScript

python -m pip install --upgrade pip
pip install -r requirements.txt

# Step 5: Copy application files
Write-Host "Step 5: Copying application files..." -ForegroundColor Green
Copy-Item -Path "kite_auto_trading" -Destination $InstallPath -Recurse -Force
Copy-Item -Path "config\*" -Destination $ConfigDir -Recurse -Force
Copy-Item -Path "strategies" -Destination $InstallPath -Recurse -Force
Copy-Item -Path ".env.example" -Destination (Join-Path $InstallPath ".env") -Force

# Copy appropriate config file
$ConfigSource = "config\$ConfigType`_trading.yaml"
if (Test-Path $ConfigSource) {
    Copy-Item -Path $ConfigSource -Destination (Join-Path $InstallPath "config.yaml") -Force
    Write-Host "Using $ConfigType trading configuration" -ForegroundColor Cyan
} else {
    Copy-Item -Path "config.yaml" -Destination $InstallPath -Force
    Write-Host "Using default configuration" -ForegroundColor Cyan
}

# Step 6: Create Windows Service (using NSSM - Non-Sucking Service Manager)
Write-Host "Step 6: Setting up Windows Service..." -ForegroundColor Green
Write-Host "Note: For Windows Service, install NSSM from https://nssm.cc/" -ForegroundColor Yellow
Write-Host "Then run: nssm install KiteTrading `"$VenvPath\Scripts\python.exe`" `"-m kite_auto_trading.main`"" -ForegroundColor Yellow

# Step 7: Create startup script
Write-Host "Step 7: Creating startup script..." -ForegroundColor Green
$StartupScript = Join-Path $InstallPath "start_trading.ps1"
@"
# Kite Auto Trading Startup Script
`$VenvPath = "$VenvPath"
`$AppPath = "$InstallPath"

Write-Host "Starting Kite Auto Trading..." -ForegroundColor Green
Set-Location `$AppPath
& "`$VenvPath\Scripts\Activate.ps1"
python -m kite_auto_trading.main
"@ | Out-File -FilePath $StartupScript -Encoding UTF8

# Step 8: Create stop script
$StopScript = Join-Path $InstallPath "stop_trading.ps1"
@"
# Kite Auto Trading Stop Script
Write-Host "Stopping Kite Auto Trading..." -ForegroundColor Yellow
Get-Process python | Where-Object {`$_.Path -like "*$InstallPath*"} | Stop-Process -Force
Write-Host "Trading application stopped" -ForegroundColor Green
"@ | Out-File -FilePath $StopScript -Encoding UTF8

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installation Path: $InstallPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit $InstallPath\.env with your Kite API credentials" -ForegroundColor White
Write-Host "2. Review and customize $InstallPath\config.yaml" -ForegroundColor White
Write-Host "3. Start the application: & '$StartupScript'" -ForegroundColor White
Write-Host "4. View logs: Get-Content $LogDir\trading.log -Wait" -ForegroundColor White
Write-Host ""
Write-Host "For Windows Service setup:" -ForegroundColor Yellow
Write-Host "1. Download NSSM from https://nssm.cc/" -ForegroundColor White
Write-Host "2. Run: nssm install KiteTrading `"$VenvPath\Scripts\python.exe`" `"-m kite_auto_trading.main`"" -ForegroundColor White
Write-Host "3. Configure service working directory to: $InstallPath" -ForegroundColor White
Write-Host ""

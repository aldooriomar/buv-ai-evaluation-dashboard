$ErrorActionPreference = 'Stop'

# BUV AI Evaluation Dashboard v2.0.0
# Solution design/build/deployment/implementation: Omar, 2026
# ASCII-only Windows PowerShell 5.1-compatible bootstrap.

$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$AppVersion = '2.0.0'
$PythonVersion = '3.13.15'
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$PythonSha256 = 'D1F04D990AEE1253D8569E8E5104E30FA9F5FA830899F14843448872D936A2CF'
$LocalPython = Join-Path $Root 'python.exe'
$DataDir = Join-Path $Root 'data'
$BackupDir = Join-Path $DataDir 'backups'
$LogDir = Join-Path $Root 'logs'
$Backend = Join-Path $DataDir 'BUV_AI_Evaluation_Backend.xlsx'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$BootstrapLog = Join-Path $LogDir 'bootstrap.log'

function Log-Line([string]$Text) {
    try { Add-Content -LiteralPath $BootstrapLog -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Text) -Encoding UTF8 } catch { }
}
function Write-Stage([string]$Text) {
    Write-Host "[BUV] $Text" -ForegroundColor Cyan
    Log-Line $Text
}
function Fail([string]$Text) {
    Log-Line ("ERROR: " + $Text)
    Write-Host ''
    Write-Host "ERROR: $Text" -ForegroundColor Red
    Write-Host "Startup log: $BootstrapLog" -ForegroundColor DarkGray
    exit 1
}

Log-Line 'Startup requested.'
Write-Host ''
Write-Host '============================================================' -ForegroundColor DarkBlue
Write-Host " BUV AI Evaluation Dashboard v$AppVersion" -ForegroundColor DarkBlue
Write-Host ' One-click local controlled release' -ForegroundColor DarkBlue
Write-Host '============================================================' -ForegroundColor DarkBlue
Write-Host ''

try {
    Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
} catch { }

if (-not [Environment]::Is64BitOperatingSystem) { Fail 'This package requires 64-bit Windows.' }

$Required = @(
    'app.py','xlsx_store.py','index.html','app.js','styles.css','version.json',
    'config\settings.json','config\governance_sources.json','config\holidays.json',
    'assets\buv_ict_header.jpg','data\BUV_AI_Evaluation_Backend.xlsx',
    'documents\BUV_AI_Usage_Guideline_v3.0.docx',
    'documents\BUV_ICT_AI_Technology_Use_Policy_2026.docx',
    'docs\README_SYSTEM.md','docs\TROUBLESHOOTING.md'
)
$Missing = @()
foreach ($Rel in $Required) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $Rel))) { $Missing += $Rel }
}
if ($Missing.Count -gt 0) {
    Write-Host 'Missing package files:' -ForegroundColor Red
    $Missing | ForEach-Object { Write-Host "  - $_" }
    Fail 'Re-extract a fresh copy of the ZIP and try again.'
}
Write-Stage 'Package files: OK'

$Manifest = Join-Path $Root 'CORE_CHECKSUMS_SHA256.txt'
if (Test-Path -LiteralPath $Manifest) {
    $Bad = @()
    foreach ($Line in Get-Content -LiteralPath $Manifest) {
        if ($Line -match '^([A-Fa-f0-9]{64})\s{2}(.+)$') {
            $Expected = $matches[1].ToUpperInvariant()
            $Rel = $matches[2]
            $Path = Join-Path $Root $Rel
            if (-not (Test-Path -LiteralPath $Path)) { $Bad += "$Rel (missing)" }
            else {
                $Actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
                if ($Actual -ne $Expected) { $Bad += "$Rel (checksum mismatch)" }
            }
        }
    }
    if ($Bad.Count -gt 0) {
        Write-Host 'Integrity check failed:' -ForegroundColor Red
        $Bad | ForEach-Object { Write-Host "  - $_" }
        Fail 'Core package files were changed or damaged. Re-extract the original BUV package.'
    }
    Write-Stage 'Core package integrity: verified'
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$WriteTest = Join-Path $DataDir ('.write_test_' + [Guid]::NewGuid().ToString('N') + '.tmp')
try {
    [System.IO.File]::WriteAllText($WriteTest, 'BUV write test')
    Remove-Item -LiteralPath $WriteTest -Force
} catch { Fail 'This folder is not writable. Move the extracted dashboard to Documents or Desktop and try again.' }
Write-Stage 'Data folder: writable'

try {
    $Stream = [System.IO.File]::Open($Backend, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $Stream.Close()
} catch { Fail 'The Excel backend is locked or not writable. Close BUV_AI_Evaluation_Backend.xlsx in Excel and try again.' }
Write-Stage 'Excel backend: available and not locked'

$PythonCmd = $null
$PythonArgsPrefix = @()
if (Test-Path -LiteralPath $LocalPython) {
    $PythonCmd = $LocalPython
    Write-Stage 'Portable Python from dashboard folder: ready'
} else {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    $PyExe = Get-Command python -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        try {
            & $PyLauncher.Source -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
            if ($LASTEXITCODE -eq 0) { $PythonCmd = $PyLauncher.Source; $PythonArgsPrefix = @('-3'); Write-Stage 'Compatible installed Python launcher found' }
        } catch { }
    }
    if (-not $PythonCmd -and $PyExe) {
        try {
            & $PyExe.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
            if ($LASTEXITCODE -eq 0) { $PythonCmd = $PyExe.Source; Write-Stage 'Compatible installed Python found' }
        } catch { }
    }
}

if (-not $PythonCmd) {
    Write-Host ''
    Write-Host 'A usable Python runtime is not present. Preparing the official portable runtime locally...' -ForegroundColor Yellow
    $TempZip = Join-Path $env:TEMP "buv-python-$PythonVersion-embed-amd64.zip"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Write-Stage "Downloading official Python $PythonVersion runtime from python.org"
        Invoke-WebRequest -Uri $PythonUrl -OutFile $TempZip -UseBasicParsing
    } catch { Fail "Portable Python could not be downloaded. Internet access to python.org may be blocked. Ask the BUV platform owner / ICT for an approved runtime-embedded copy. Details: $($_.Exception.Message)" }

    $ActualHash = (Get-FileHash -LiteralPath $TempZip -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($ActualHash -ne $PythonSha256) {
        Remove-Item -LiteralPath $TempZip -Force -ErrorAction SilentlyContinue
        Fail 'The downloaded Python runtime failed its SHA-256 integrity check. Nothing was installed.'
    }
    Write-Stage 'Python download integrity: verified'
    try {
        Expand-Archive -LiteralPath $TempZip -DestinationPath $Root -Force
        Get-ChildItem -LiteralPath $Root -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'python*' -or $_.Extension -in '.pyd','.dll','.cat' } | Unblock-File -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $TempZip -Force -ErrorAction SilentlyContinue
    } catch { Fail "The portable Python runtime could not be prepared. Details: $($_.Exception.Message)" }
    if (-not (Test-Path -LiteralPath $LocalPython)) { Fail 'Portable Python preparation completed without python.exe. Re-extract the package and try again.' }
    $PythonCmd = $LocalPython
    $PythonArgsPrefix = @()
    Write-Stage "Portable Python $PythonVersion prepared locally; no Administrator rights used"
}

Write-Stage 'Running dashboard self-test'
& $PythonCmd @PythonArgsPrefix '.\app.py' '--self-test'
if ($LASTEXITCODE -ne 0) { Fail 'The dashboard self-test failed. Do not enter institutional data until the package is repaired.' }

$InitialMarker = Join-Path $BackupDir '.initial_baseline_created'
if (-not (Test-Path -LiteralPath $InitialMarker)) {
    try {
        $Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        Copy-Item -LiteralPath $Backend -Destination (Join-Path $BackupDir "INITIAL_PRISTINE_BACKEND_$Stamp.xlsx") -Force
        Set-Content -LiteralPath $InitialMarker -Value "Created $(Get-Date -Format o)" -Encoding ASCII
        Write-Stage 'Initial recovery copy: created'
    } catch { Write-Host '[BUV] Warning: initial recovery copy could not be created. The dashboard can still run.' -ForegroundColor Yellow; Log-Line 'WARNING: initial recovery copy failed.' }
}

Write-Host ''
Write-Host 'READY - opening the BUV AI Evaluation Dashboard.' -ForegroundColor Green
Write-Host 'Keep this window open while the dashboard is in use.' -ForegroundColor Yellow
Write-Host 'The browser should open automatically.' -ForegroundColor Yellow
Write-Host ''
Log-Line 'Self-test passed; starting local application.'

$env:PYTHONDONTWRITEBYTECODE = '1'
& $PythonCmd @PythonArgsPrefix '.\app.py'
$ExitCode = $LASTEXITCODE
if ($ExitCode -ne 0) { Fail "The dashboard stopped with exit code $ExitCode." }
Log-Line 'Dashboard stopped normally.'
exit 0

# Gemvis one-click run for Windows PowerShell.
# Starts llama-server + backend, opens browser.
# Run: .\scripts\start_windows.ps1  (or double-click scripts\start_windows.bat)
# Stop: Ctrl+C or close the console (child processes are cleaned up).

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
}
Refresh-Path

# ---- Load .env ----
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match "^\s*([^#=][^=]*)=(.*)$") {
            $name  = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

$LlamaPort   = if ($env:LLAMA_PORT)   { $env:LLAMA_PORT }   else { "8080" }
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$LlmModel    = if ($env:LLM_MODEL)    { $env:LLM_MODEL }    else { "unsloth/gemma-4-E2B-it-GGUF:Q4_K_M" }

New-Item -ItemType Directory -Force -Path .gemvis | Out-Null

# ---- Child process tracking + cleanup ----
$script:LlamaProc   = $null
$script:BackendProc = $null

function Cleanup {
    Write-Host "`n[shutdown] cleaning up child processes"
    if ($script:BackendProc -and -not $script:BackendProc.HasExited) {
        Stop-Process -Id $script:BackendProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($script:LlamaProc -and -not $script:LlamaProc.HasExited) {
        Stop-Process -Id $script:LlamaProc.Id -Force -ErrorAction SilentlyContinue
    }
}
Register-EngineEvent PowerShell.Exiting -Action { Cleanup } | Out-Null

function Test-Endpoint($port, $path) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$port$path" -UseBasicParsing -TimeoutSec 1
        return $true
    } catch { return $false }
}

# ---- 1. llama-server ----
if (Test-Endpoint $LlamaPort "/v1/models") {
    Write-Host "[1/3] llama-server already running (port $LlamaPort)"
} else {
    if (-not (Get-Command llama-server -ErrorAction SilentlyContinue)) {
        Write-Host "[FAIL] llama-server not found. Run scripts\setup_windows.bat first." -ForegroundColor Red
        Write-Host "       (If setup already ran, open a new PowerShell and try again.)" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[1/3] starting llama-server in a new window (first run downloads ~2GB model)"
    # Vision support: locate mmproj file in HF cache and pass it explicitly
    # (-hf alone doesn't always auto-load the projector — be defensive)
    $hfCache  = Join-Path $env:USERPROFILE ".cache\huggingface\hub"
    $mmproj   = $null
    if (Test-Path $hfCache) {
        $mmproj = Get-ChildItem -Path $hfCache -Recurse -Filter "mmproj*.gguf" -ErrorAction SilentlyContinue |
                  Select-Object -First 1 -ExpandProperty FullName
    }
    $llamaArgs = @("-hf", $LlmModel, "-ngl", "999",
                   "--host", "127.0.0.1", "--port", $LlamaPort,
                   "--ctx-size", "128000")
    if ($mmproj) {
        Write-Host "      Vision mmproj: $mmproj"
        $llamaArgs += @("--mmproj", $mmproj)
    } else {
        Write-Host "      [info] mmproj not in HF cache yet - -hf will download on first run"
    }
    $script:LlamaProc = Start-Process -FilePath "llama-server" `
        -ArgumentList $llamaArgs `
        -RedirectStandardOutput ".gemvis\llama-server.log" `
        -RedirectStandardError  ".gemvis\llama-server.err.log" `
        -PassThru -NoNewWindow
    $script:LlamaProc.Id | Out-File ".gemvis\llama-server.pid"

    Write-Host "      waiting for ready (max 120s incl. model download)..."
    for ($i = 1; $i -le 120; $i++) {
        if (Test-Endpoint $LlamaPort "/v1/models") {
            Write-Host "      OK ($i s)"
            break
        }
        if ($script:LlamaProc.HasExited) {
            Write-Host "[FAIL] llama-server exited unexpectedly. See log:" -ForegroundColor Red
            Write-Host "       Get-Content .gemvis\llama-server.err.log" -ForegroundColor Red
            Read-Host "Press Enter to exit"
            exit 1
        }
        Start-Sleep -Seconds 1
    }
}

# ---- 2. backend ----
$venvPython = ".\venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[FAIL] venv not found. Run scripts\setup_windows.bat first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[2/3] starting backend (port $BackendPort)"
$script:BackendProc = Start-Process -FilePath $venvPython `
    -ArgumentList "run.py" `
    -RedirectStandardOutput ".gemvis\backend.log" `
    -RedirectStandardError  ".gemvis\backend.err.log" `
    -PassThru -NoNewWindow
$script:BackendProc.Id | Out-File ".gemvis\backend.pid"

Write-Host "      waiting for ready..."
for ($i = 1; $i -le 30; $i++) {
    if (Test-Endpoint $BackendPort "/") {
        Write-Host "      OK ($i s)"
        break
    }
    if ($script:BackendProc.HasExited) {
        Write-Host "[FAIL] backend exited unexpectedly. See log:" -ForegroundColor Red
        Write-Host "       Get-Content .gemvis\backend.err.log" -ForegroundColor Red
        Cleanup
        Read-Host "Press Enter to exit"
        exit 1
    }
    Start-Sleep -Seconds 1
}

# ---- 3. browser ----
$url = "http://localhost:$BackendPort"
Write-Host "[3/3] opening browser: $url"
Start-Process $url

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "Gemvis running - Ctrl+C or close window to stop" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host "   URL:           $url"
Write-Host "   Backend log:   Get-Content -Wait .gemvis\backend.log"
Write-Host "   LLM log:       Get-Content -Wait .gemvis\llama-server.err.log"
Write-Host ""

try {
    Wait-Process -Id $script:BackendProc.Id
} finally {
    Cleanup
}

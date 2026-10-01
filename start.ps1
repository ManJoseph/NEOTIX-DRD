param(
    [switch]$CheckOnly,
    [switch]$SmokeTest,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

function Assert-CommandSucceeded([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed. Read the output above." }
}

Push-Location $projectRoot
try {
    foreach ($port in @($BackendPort, $FrontendPort)) {
        $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
        if ($listener) { throw "Port $port is already in use. Stop your old development server or choose other ports." }
    }
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        & py -3.13 -m venv .venv
        Assert-CommandSucceeded "Virtual environment creation"
    }
    & $pythonPath -m pip install -r requirements.txt
    Assert-CommandSucceeded "Backend dependency installation"
    & $pythonPath scripts/configure_environment.py
    Assert-CommandSucceeded "Environment configuration"

    # PostgreSQL must be installed. Start its Windows service if it is stopped.
    $postgresService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($postgresService -and $postgresService.Status -ne "Running") {
        Start-Service -Name $postgresService.Name
    }
    & $pythonPath scripts/create_database.py
    Assert-CommandSucceeded "Database creation"
    & $pythonPath manage.py migrate --noinput
    Assert-CommandSucceeded "Migrations"
    & $pythonPath manage.py check
    Assert-CommandSucceeded "Django configuration check"

    & $pythonPath manage.py shell -c "from desk.models import User; import sys; sys.exit(0 if User.objects.filter(role='admin', is_active=True).exists() else 1)"
    if ($LASTEXITCODE -ne 0) {
        if ($CheckOnly -or $SmokeTest) { throw "No active admin. Run start.ps1 normally to create one interactively." }
        & $pythonPath manage.py createsuperuser
        Assert-CommandSucceeded "Initial admin creation"
    }

    Push-Location (Join-Path $projectRoot "frontend")
    try {
        & npm.cmd ci
        Assert-CommandSucceeded "Frontend dependency installation"
        & npm.cmd run build
        Assert-CommandSucceeded "Frontend build"
    } finally { Pop-Location }
    if ($CheckOnly) { Write-Host "Setup checks passed."; return }

    $logDirectory = Join-Path $projectRoot ".run"
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $backendProcess = $null
    $frontendProcess = $null
    $previousBackendUrl = $env:BACKEND_URL
    try {
        $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @("manage.py", "runserver", "127.0.0.1:$BackendPort", "--noreload") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logDirectory\backend.log" -RedirectStandardError "$logDirectory\backend-errors.log"
        $env:BACKEND_URL = "http://127.0.0.1:$BackendPort"
        $viteEntry = Join-Path $projectRoot "frontend\node_modules\vite\bin\vite.js"
        $viteArguments = "`"$viteEntry`" --host 127.0.0.1 --port $FrontendPort"
        $frontendProcess = Start-Process -FilePath (Get-Command node).Source -ArgumentList $viteArguments -WorkingDirectory (Join-Path $projectRoot "frontend") -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logDirectory\frontend.log" -RedirectStandardError "$logDirectory\frontend-errors.log"
        Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
        Write-Host "Backend: http://127.0.0.1:$BackendPort"
        Write-Host "Logs: .run/*.log. Keep this terminal open; Ctrl+C stops both servers."

        if ($SmokeTest) {
            $ready = $false
            for ($attempt = 0; $attempt -lt 30; $attempt++) {
                try {
                    $page = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -UseBasicParsing -TimeoutSec 2
                    if ($page.StatusCode -eq 200 -and $page.Content.Contains("NEOTIX")) { $ready = $true; break }
                } catch { Start-Sleep -Seconds 1 }
            }
            if (-not $ready) { throw "Frontend did not become ready; inspect .run logs." }
            $validated = $false
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/api/auth/login/" -Method Post -ContentType "application/json" -Body "{}" -UseBasicParsing -TimeoutSec 5 | Out-Null
            } catch {
                if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 400) { $validated = $true }
                else { throw }
            }
            if (-not $validated) { throw "Expected Django login validation through the frontend proxy." }
            Write-Host "Startup smoke test passed: frontend page and Django API proxy."
        } else {
            while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) { Start-Sleep -Seconds 1 }
            throw "A development server exited. Inspect .run logs."
        }
    } finally {
        $env:BACKEND_URL = $previousBackendUrl
        if ($backendProcess -and -not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id }
        if ($frontendProcess -and -not $frontendProcess.HasExited) { Stop-Process -Id $frontendProcess.Id }
    }
} finally { Pop-Location }

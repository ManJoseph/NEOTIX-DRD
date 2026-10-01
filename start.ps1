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

    & $pythonPath manage.py seed_reviewers
    Assert-CommandSucceeded "Reviewer account setup"

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
        # Vite can start before Django on a fresh installation. Wait for both.
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if ($backendProcess.HasExited -or $frontendProcess.HasExited) { throw "A server exited during startup; inspect .run logs." }
            $backendReady = $false
            $frontendReady = $false
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
            } catch {
                # Health requires a token, so 401 confirms the API is accepting requests.
                if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { $backendReady = $true }
            }
            try {
                $page = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -UseBasicParsing -TimeoutSec 2
                $frontendReady = $page.StatusCode -eq 200 -and $page.Content.Contains("NEOTIX")
            } catch { }
            if ($backendReady -and $frontendReady) { $ready = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw "Servers did not become ready; inspect .run logs." }
        Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
        Write-Host "Backend: http://127.0.0.1:$BackendPort"
        Write-Host "Logs: .run/*.log. Keep this terminal open; Ctrl+C stops both servers."

        if ($SmokeTest) {
            $validated = $false
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/api/auth/login/" -Method Post -ContentType "application/json" -Body "{}" -UseBasicParsing -TimeoutSec 5 | Out-Null
            } catch {
                if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 400) { $validated = $true }
                else { throw }
            }
            if (-not $validated) { throw "Expected Django login validation through the frontend proxy." }
            $accounts = Get-Content -LiteralPath "$projectRoot\.run\reviewer-accounts.json" -Raw | ConvertFrom-Json
            foreach ($entry in $accounts.PSObject.Properties) {
                $account = $entry.Value
                if (-not $account.password) { continue }
                $loginBody = @{ username = $account.username; password = $account.password } | ConvertTo-Json
                $login = Invoke-RestMethod -Uri "http://127.0.0.1:$FrontendPort/api/auth/login/" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec 5
                if ($login.user.role -ne $account.role) { throw "Reviewer role verification failed." }
                $headers = @{ Authorization = "Token $($login.token)" }
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:$FrontendPort/health" -Headers $headers -TimeoutSec 5
                if ($health.database -ne "ok") { throw "Database health verification failed." }
                Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/api/auth/logout/" -Method Post -Headers $headers -UseBasicParsing -TimeoutSec 5 | Out-Null
            }
            Write-Host "Startup smoke test passed: frontend, API proxy, seeded logins/roles, database health, and logout."
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

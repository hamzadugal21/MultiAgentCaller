param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000,
    [string]$TunnelHost = ""
)

$ErrorActionPreference = "Stop"

$required = @(
    "HIREFLOW_QA_MODE",
    "QA_DATABASE_ISOLATION_ACK",
    "QA_DATABASE_URL",
    "QA_DJANGO_SECRET_KEY"
)
foreach ($name in $required) {
    if (-not (Test-Path -LiteralPath "Env:$name")) {
        throw "$name must be supplied in this private PowerShell session."
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$daphne = Join-Path $projectRoot ".venv\Scripts\daphne.exe"

$env:DJANGO_SETTINGS_MODULE = "config.settings_qa"
$env:DJANGO_READ_DOT_ENV = "False"
$env:HIREFLOW_QA_MODEL_ACTIONS = "0"
$env:HIREFLOW_QA_BROWSER_VOICE = "1"
$env:PYTHONPATH = $backendRoot
if ($TunnelHost) {
    $env:QA_TUNNEL_HOST = $TunnelHost
} else {
    Remove-Item -LiteralPath "Env:QA_TUNNEL_HOST" -ErrorAction SilentlyContinue
}

Push-Location $projectRoot
try {
    & $python "scripts\verify_qa_database.py"
    if ($LASTEXITCODE -ne 0) { throw "QA database verification failed." }
    & $python "backend\manage.py" check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
} finally {
    Pop-Location
}

Push-Location $backendRoot
try {
    & $daphne --access-log NUL --no-server-name --websocket-max-message-size 16384 -b 127.0.0.1 -p $Port config.asgi:application
} finally {
    Pop-Location
}

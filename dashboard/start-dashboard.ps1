# start-dashboard.ps1
# Arranca el Coesita Dashboard en http://localhost:5050

$venvPython = "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe"
$dashboardScript = "$PSScriptRoot\app.py"

# Cargar variables de entorno desde .env si existe
$envFile = "$env:USERPROFILE\.hermes\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

Write-Host "Coesita Dashboard -> http://localhost:5050" -ForegroundColor Cyan
& $venvPython $dashboardScript

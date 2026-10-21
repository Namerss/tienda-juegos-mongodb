# Levanta los 3 nodos del Replica Set (Windows / PowerShell).
# Uso: .\infra\iniciar-nodos.ps1 inicial   (Pasos 1 y 2)
#      .\infra\iniciar-nodos.ps1 seguro    (Paso 3)
param([ValidateSet("inicial", "seguro")][string]$Modo = "inicial")

Set-Location (Join-Path $PSScriptRoot "..")
"data\nodo1", "data\nodo2", "data\arbitro", "data\pids", "logs" |
    ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

foreach ($nodo in "nodo1", "nodo2", "arbitro") {
    $p = Start-Process mongod -ArgumentList "--config", "config\$Modo\$nodo.conf" `
        -WindowStyle Hidden -PassThru
    Set-Content -Path "data\pids\$nodo.pid" -Value $p.Id -Encoding ascii
    Write-Host "$nodo iniciado en modo $Modo (PID $($p.Id))"
}
Write-Host "Logs en .\logs - si un nodo no arranca, revisa su .log"

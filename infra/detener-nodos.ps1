# Detiene los 3 nodos (Windows / PowerShell).
Set-Location (Join-Path $PSScriptRoot "..")
foreach ($nodo in "nodo1", "nodo2", "arbitro") {
    $f = "data\pids\$nodo.pid"
    if (Test-Path $f) {
        Stop-Process -Id (Get-Content $f) -ErrorAction SilentlyContinue
        Remove-Item $f
        Write-Host "$nodo detenido"
    }
}

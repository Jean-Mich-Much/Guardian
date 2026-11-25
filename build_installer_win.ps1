param(
    [string]$Compiler = ""
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$application = Join-Path $root "dist\Guardian-installed.exe"
if (-not (Test-Path -LiteralPath $application -PathType Leaf)) {
    throw "Compilez d'abord Guardian avec build_win_11.ps1 -Installed."
}

if (-not $Compiler) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        $Compiler = $command.Source
    } else {
        $candidates = @(
            (Join-Path ${env:ProgramFiles} "Inno Setup 7\ISCC.exe"),
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
        )
        $Compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler -PathType Leaf)) {
    throw "Compilateur Inno Setup introuvable. Installez-le ou indiquez son chemin avec -Compiler."
}

& $Compiler (Join-Path $root "installer\guardian.iss")
if ($LASTEXITCODE -ne 0) {
    throw "La compilation de l'installateur a échoué."
}
Write-Host "Installateur créé : $(Join-Path $root 'dist\Installer-Guardian.exe')"

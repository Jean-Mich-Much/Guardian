# Compilation Windows sérialisée, icône intégrée et test réel avant livraison.
param(
    [switch]$Installed
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$dist = Join-Path $root "dist"
$stage = Join-Path $dist "build-staging"
$lockPath = Join-Path $root ".guardian-build.lock"
$buildCache = Join-Path $root ".build-cache"
$lockStream = $null

try {
    try {
        $lockStream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    }
    catch {
        throw "Une compilation Guardian est déjà en cours. Attendez sa fin avant d'en relancer une."
    }

    Set-Location $root
    New-Item -ItemType Directory -Force -Path $dist, $buildCache | Out-Null

    $final = Join-Path $dist $(if ($Installed) { "Guardian-installed.exe" } else { "Guardian.exe" })
    $legacyExecutable = Join-Path $dist "main_win_11.exe"
    $runningBuilds = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -in @("Guardian.exe", "main_win_11.exe") -and
            $_.ExecutablePath -in @($final, $legacyExecutable)
        }
    if ($runningBuilds) {
        throw "Fermez Guardian avant de compiler sa nouvelle version."
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "tools\create_windows_icon.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "L'icône Guardian n'a pas pu être créée."
    }

    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    $buildReport = Join-Path $stage "guardian-build-report.xml"

    $env:ZIG_LOCAL_CACHE_DIR = Join-Path $buildCache "zig-local"
    $env:ZIG_GLOBAL_CACHE_DIR = Join-Path $buildCache "zig-global"
    New-Item -ItemType Directory -Force -Path $env:ZIG_LOCAL_CACHE_DIR, $env:ZIG_GLOBAL_CACHE_DIR | Out-Null

    $jobs = [Math]::Max(1, [Math]::Min(4, [Environment]::ProcessorCount))
    $buildVersion = (Get-Date).ToString("yyyy.MM.dd.HHmm")
    $nuitkaArguments = @(
        "-3.12",
        "-m", "nuitka",
        "--onefile",
        "--onefile-cache-mode=cached",
        "--zig",
        "--include-windows-runtime-dlls=no",
        "--assume-yes-for-downloads",
        "--jobs=$jobs",
        "--windows-console-mode=disable",
        "--windows-icon-from-ico=assets/guardian.ico",
        "--company-name=Guardian",
        "--product-name=Guardian",
        "--product-version=$buildVersion",
        "--output-filename=Guardian.exe",
        "--include-data-dir=frontend=frontend",
        "--include-data-file=LICENSE=frontend/LICENSE.txt",
        "--include-data-file=THIRD_PARTY_NOTICES.md=frontend/THIRD_PARTY_NOTICES.txt",
        "--include-data-dir=doc=doc",
        "--report=$buildReport",
        "--output-dir=$stage",
        "main_win_11.py"
    )
    if ($Installed) {
        $nuitkaArguments = @(
            $nuitkaArguments[0..($nuitkaArguments.Length - 2)]
            '--onefile-tempdir-spec={CACHE_DIR}\Guardian\Installed\{VERSION}'
            $nuitkaArguments[-1]
        )
    }

    & py @nuitkaArguments
    if ($LASTEXITCODE -ne 0) {
        throw "La compilation Nuitka a échoué. L'exécutable précédent est conservé."
    }
    if (-not (Test-Path -LiteralPath $buildReport)) {
        throw "Le rapport Nuitka requis pour vérifier les DLL incluses est absent. L'exécutable précédent est conservé."
    }
    [xml]$reportDocument = Get-Content -LiteralPath $buildReport -Raw
    $includedDlls = $reportDocument.SelectNodes("//included_dll")
    foreach ($runtimeDll in @("vcruntime140.dll", "vcruntime140_1.dll")) {
        $bundled = $includedDlls | Where-Object {
            $_.GetAttribute("ignored") -eq "no" -and
            $_.GetAttribute("name").Equals(
                $runtimeDll,
                [StringComparison]::OrdinalIgnoreCase
            ) -and
            $_.GetAttribute("dest_path").Equals(
                $runtimeDll,
                [StringComparison]::OrdinalIgnoreCase
            )
        }
        if (-not $bundled) {
            throw "La DLL $runtimeDll n'est pas incluse à côté de l'application. L'exécutable précédent est conservé."
        }
    }

    $candidate = Join-Path $stage "Guardian.exe"
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "Nuitka n'a pas produit l'exécutable attendu. L'exécutable précédent est conservé."
    }
    $maxExecutableBytes = 256MB
    $candidateBytes = (Get-Item -LiteralPath $candidate).Length
    if ($candidateBytes -gt $maxExecutableBytes) {
        $candidateSize = [Math]::Round($candidateBytes / 1MB, 1)
        throw "Le nouvel exécutable pèse $candidateSize Mio, au-delà de la limite de 256 Mio. L'exécutable précédent est conservé; une décision est nécessaire."
    }

    $selfTest = Start-Process `
        -FilePath $candidate `
        -ArgumentList "--self-test" `
        -PassThru `
        -WindowStyle Hidden
    if (-not $selfTest.WaitForExit(90000)) {
        Stop-Process -Id $selfTest.Id -Force -ErrorAction SilentlyContinue
        throw "Le test de démarrage a dépassé son délai. L'exécutable précédent est conservé."
    }
    if ($selfTest.ExitCode -ne 0) {
        throw "L'auto-test du document ou des fonctions Guardian a échoué. L'exécutable précédent est conservé."
    }

    Add-Type -AssemblyName System.Drawing
    $embeddedIcon = [System.Drawing.Icon]::ExtractAssociatedIcon($candidate)
    if ($null -eq $embeddedIcon) {
        throw "L'icône de Guardian n'a pas été intégrée à l'exécutable."
    }
    $embeddedIcon.Dispose()

    $replaceExisting = Test-Path -LiteralPath $final
    if ($replaceExisting) {
        $runningBuilds = Get-CimInstance Win32_Process |
            Where-Object {
                $_.Name -in @("Guardian.exe", "main_win_11.exe") -and
                $_.ExecutablePath -in @($final, $legacyExecutable)
            }
        if ($runningBuilds) {
            throw "Guardian a été ouvert pendant la compilation. Fermez-le avant d'installer la nouvelle version; l'exécutable précédent est conservé."
        }
    }

    $replacement = Join-Path $dist "Guardian.exe.new"
    Copy-Item -LiteralPath $candidate -Destination $replacement -Force
    if ($replaceExisting) {
        $backup = Join-Path $dist "Guardian.exe.previous.$buildVersion"
        [System.IO.File]::Replace($replacement, $final, $backup, $true)
        try {
            Remove-Item -LiteralPath $backup -Force -ErrorAction Stop
        }
        catch [System.IO.IOException] {
            Write-Warning "Le nouvel exécutable est installé, mais la copie précédente est verrouillée et conservée : $backup"
        }
        catch [System.UnauthorizedAccessException] {
            Write-Warning "Le nouvel exécutable est installé, mais la copie précédente n'a pas pu être supprimée et reste conservée : $backup"
        }
    }
    else {
        [System.IO.File]::Move($replacement, $final)
    }

    if (-not $Installed -and (Test-Path -LiteralPath $legacyExecutable)) {
        Remove-Item -LiteralPath $legacyExecutable -Force
    }
    Remove-Item -LiteralPath $stage -Recurse -Force
    foreach ($oldBuildDirectory in @(
        (Join-Path $dist "main_win_11.build"),
        (Join-Path $dist "main_win_11.dist"),
        (Join-Path $dist "main_win_11.onefile-build"),
        (Join-Path $dist "Guardian.build"),
        (Join-Path $dist "Guardian.dist"),
        (Join-Path $dist "Guardian.onefile-build")
    )) {
        if (Test-Path -LiteralPath $oldBuildDirectory) {
            Remove-Item -LiteralPath $oldBuildDirectory -Recurse -Force
        }
    }
    Write-Host "Compilation, icône et auto-test réussis : $final"
}
finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
}

param(
    [string]$PythonLauncher = "py"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SpecFile = Join-Path $ProjectRoot "SmartFinance.spec"
$InstallerScript = Join-Path $ProjectRoot "installer\SmartFinance.nsi"
$BuildStage = Join-Path $env:TEMP ("SmartFinance-build-" + [guid]::NewGuid().ToString("N"))
$AppDist = Join-Path $BuildStage "dist\SmartFinance"
$SetupPath = Join-Path $ProjectRoot "dist\SmartFinance-Setup.exe"
$TestData = Join-Path $env:TEMP ("SmartFinance-test-" + [guid]::NewGuid().ToString("N"))
$WorkPath = Join-Path $BuildStage "work"

Push-Location $ProjectRoot
try {
    & $PythonLauncher -3.15 -m PyInstaller --version
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller não está disponível no Python 3.15. Instale Recursos\Dependencias\requirements-build.txt."
    }

    New-Item -ItemType Directory -Path $TestData -Force | Out-Null
    $PreviousDataDir = $env:SMARTFINANCE_DATA_DIR
    $env:SMARTFINANCE_DATA_DIR = $TestData
    try {
        & $PythonLauncher -3.15 -m unittest discover -s Recursos\Testes -t . -p test_app.py
        if ($LASTEXITCODE -ne 0) {
            throw "Os testes do SmartFinance falharam."
        }
    }
    finally {
        $env:SMARTFINANCE_DATA_DIR = $PreviousDataDir
    }

    & $PythonLauncher -3.15 -m PyInstaller --noconfirm --clean --distpath (Join-Path $BuildStage "dist") --workpath $WorkPath $SpecFile
    if ($LASTEXITCODE -ne 0) {
        throw "O empacotamento do executável falhou."
    }

    New-Item -ItemType Directory -Path (Split-Path -Parent $SetupPath) -Force | Out-Null
    $Nsis = Get-Command makensis -ErrorAction SilentlyContinue
    $NsisPath = if ($Nsis) { $Nsis.Source } else { $null }
    if (-not $NsisPath) {
        $NsisCandidates = @(
            (Join-Path ${env:ProgramFiles(x86)} "NSIS\makensis.exe"),
            (Join-Path $env:ProgramFiles "NSIS\makensis.exe")
        )
        foreach ($candidate in $NsisCandidates) {
            if (Test-Path -LiteralPath $candidate) {
                $NsisPath = $candidate
                break
            }
        }
    }
    if (-not $NsisPath) {
        throw "NSIS not found. Install NSIS or add makensis.exe to PATH."
    }
    & $NsisPath "/DAPP_DIR=$AppDist" "/DOUTPUT_EXE=$SetupPath" $InstallerScript
    if ($LASTEXITCODE -ne 0) {
        throw "A criação do instalador NSIS falhou."
    }

    Write-Host "Instalador criado: $SetupPath"
}
finally {
    if (Test-Path -LiteralPath $TestData) {
        Remove-Item -LiteralPath $TestData -Recurse -Force
    }
    if (Test-Path -LiteralPath $BuildStage) {
        Remove-Item -LiteralPath $BuildStage -Recurse -Force
    }
    Pop-Location
}

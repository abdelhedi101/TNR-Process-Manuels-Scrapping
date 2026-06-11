param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('AWB', 'BMCE')]
    [string]$Project,

    [Parameter(Mandatory = $true)]
    [string]$Module,

    [string]$MenuPathFile,

    [string]$ScreenshotDir = 'screenshots',

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workspace = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $workspace '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
    throw "Python venv introuvable: $pythonExe"
}

$projectConfigs = @{
    'AWB' = @{
        Script = 'non_regression_awb.py'
        Auth = @{
            Username = 'migration'
            Password = 'Vermeg+123'
            Domain = 'awb'
            Type = 'standard'
        }
        Modules = @{
            'MegaCommon'  = @{ Url = 'http://10.1.140.244:9080/MegaCommon/login.jsp'; Menu = 'Projects/AWB/common/awb_common.txt' }
            'MegaCor'     = @{ Url = 'http://10.1.140.244:9081/MegaCor/login.jsp'; Menu = 'Projects/AWB/core/awb_core.txt' }
            'MegaCustody' = @{ Url = 'http://10.1.140.244:9082/MegaCustody/login.jsp'; Menu = 'Projects/AWB/custody/awb_custody.txt' }
            'MegaTrade'   = @{ Url = 'http://10.1.140.244:9083/MegaTrade/WebApp.jsp'; Menu = 'Projects/AWB/Trade/awb_trade.txt' }
            'MegaIssuer'  = @{ Url = 'http://10.1.140.244:9084/MegaIssuer/WebApp.jsp'; Menu = 'Projects/AWB/Issuer/awb_issuer.txt' }
        }
    }
    'BMCE' = @{
        Script = 'non_regression_bmce.py'
        Auth = @{
            Username = 'ADMINBMCE'
            Password = '1234'
            Domain = 'BMCE BANK'
            Type = 'standard'
        }
        Modules = @{
            'MegaCommon'     = @{ Url = 'http://10.1.146.163:9080/MegaCommon/WebApp.html'; Menu = 'Projects/BMCE/Common/bmce_common.txt'; Auth = @{ Username = 'migration'; Password = 'Vermeg+123'; Domain = 'BMCE BANK'; Type = 'standard' } }
            'MegaCor'        = @{ Url = 'http://10.1.146.163:9081/MegaCor/WebApp.html'; Menu = 'Projects/BMCE/Cor/bmce_core.txt' ; Auth = @{ Username = 'migration'; Password = 'Vermeg+123'; Domain = 'BMCE BANK'; Type = 'standard' } }
            'MegaCustody'    = @{ Url = 'http://10.1.146.163:9082/MegaCustody/WebApp.html'; Menu = 'Projects/BMCE/Custody/bmce_custody.txt'; Auth = @{ Username = 'migration'; Password = 'Vermeg+123'; Domain = 'BMCE BANK'; Type = 'standard' } }
            'MegaLend'       = @{ Url = 'http://10.1.146.163:9083/MegaLend/WebApp.html'; Menu = 'Projects/BMCE/MegaLend/bmce_lend.txt' }
            'MegaTrade'      = @{ Url = 'http://10.1.146.163:9084/MegaTrade/WebApp.html'; Menu = 'Projects/BMCE/Cor/bmce_core.txt' }
            'MegaAccounting' = @{ Url = 'http://10.1.146.163:9085/MegaAccounting/WebApp.html'; Menu = 'Projects/BMCE/Cor/bmce_core.txt' }
            'MegaCompliance' = @{ Url = 'http://10.1.146.163:9086/MegaCompliance/WebApp.html'; Menu = 'Projects/BMCE/Compliance/bmce_compliance.txt' }
            'MegaIssuer'     = @{ Url = 'http://10.1.146.163:9087/MegaIssuer/WebApp.html'; Menu = 'Projects/BMCE/Cor/bmce_core.txt' }
        }
    }
}

if (-not $projectConfigs.ContainsKey($Project)) {
    throw "Projet non supporte: ${Project}"
}

$config = $projectConfigs[$Project]
if (-not $config.Modules.ContainsKey($Module)) {
    $available = ($config.Modules.Keys | Sort-Object) -join ', '
    throw "Module non supporte pour ${Project}: ${Module}. Modules disponibles: ${available}"
}

$moduleConfig = $config.Modules[$Module]
$authConfig = if ($moduleConfig.ContainsKey('Auth')) { $moduleConfig.Auth } else { $config.Auth }
$scriptPath = Join-Path $workspace $config.Script
if (-not (Test-Path $scriptPath)) {
    throw "Script introuvable: $scriptPath"
}

if ([string]::IsNullOrWhiteSpace($MenuPathFile)) {
    $MenuPathFile = $moduleConfig.Menu
}

$resolvedMenuPath = if ([System.IO.Path]::IsPathRooted($MenuPathFile)) {
    $MenuPathFile
} else {
    Join-Path $workspace $MenuPathFile
}
if (-not (Test-Path $resolvedMenuPath)) {
    throw "Menu path introuvable: $resolvedMenuPath"
}

$resolvedScreenshotDir = Join-Path $workspace $ScreenshotDir
if (-not (Test-Path $resolvedScreenshotDir)) {
    New-Item -ItemType Directory -Path $resolvedScreenshotDir -Force | Out-Null
}

$env:MENU_PATH_FILE = $resolvedMenuPath
$env:PROJECT_SLUG = $Project.ToLowerInvariant()
$env:MENU_CATEGORY_SLUG = $Module
$env:SCREENSHOT_DIR = $resolvedScreenshotDir
$env:MODULE_URL = $moduleConfig.Url
$env:AUTH_USERNAME = $authConfig.Username
$env:AUTH_PASSWORD = $authConfig.Password
$env:AUTH_DOMAIN = $authConfig.Domain
$env:AUTH_TYPE = $authConfig.Type

Write-Host "Project          : $Project"
Write-Host "Module           : $Module"
Write-Host "Script           : $scriptPath"
Write-Host "MENU_PATH_FILE   : $env:MENU_PATH_FILE"
Write-Host "PROJECT_SLUG     : $env:PROJECT_SLUG"
Write-Host "MENU_CATEGORY_SLUG: $env:MENU_CATEGORY_SLUG"
Write-Host "SCREENSHOT_DIR   : $env:SCREENSHOT_DIR"
Write-Host "MODULE_URL       : $env:MODULE_URL"
Write-Host "AUTH_USERNAME    : $env:AUTH_USERNAME"
Write-Host "AUTH_DOMAIN      : $env:AUTH_DOMAIN"
Write-Host "AUTH_TYPE        : $env:AUTH_TYPE"

if ($DryRun) {
    Write-Host 'DryRun active: execution ignoree.'
    return
}

Push-Location $workspace
try {
    & $pythonExe $scriptPath
} finally {
    Pop-Location
}

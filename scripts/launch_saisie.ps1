param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('AWB', 'CDG', 'BMCE')]
    [string]$Project,

    [Parameter(Mandatory = $true)]
    [ValidateSet('MegaCommon', 'MegaCustody')]
    [string]$Module,

    [string]$MenuPathFile,

    [string]$ScreenshotDir = 'screenshots',

    [ValidateSet('Saisie', 'ProcessRL')]
    [string]$RunProfile = 'Saisie',

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
        Script = 'saisie_awb.py'
        Auth = @{
            Username = 'migration'
            Password = 'Vermeg+123'
            Domain = 'awb'
            Type = 'standard'
        }
        Modules = @{
            'MegaCommon'  = @{ Url = 'http://10.1.140.244:9080/MegaCommon/login.jsp'; Menu = 'Projects/AWB/common/saisie.txt' }
            'MegaCustody' = @{ Url = 'http://10.1.140.244:9082/MegaCustody/login.jsp'; Menu = 'Projects/AWB/custody/saisie.txt' }
        }
    }
    'CDG' = @{
        Script = 'saisie_CDG.py'
        Auth = @{
            Username = 'migration'
            Password = 'Vermeg+123'
            Domain = 'CDG CAPITAL'
            Type = 'keycloak'
        }
        Modules = @{
            'MegaCommon'  = @{ Url = 'https://10.1.140.42/MegaCommon/'; Menu = 'Projects/CDG/common menu/cdg_common.txt' }
            'MegaCustody' = @{ Url = 'https://10.1.140.42/MegaCustody/'; Menu = 'Projects/CDG/Custody menu/saisie.txt' }
        }
    }
    'BMCE' = @{
        Script = 'saisie_bmce.py'
        Auth = @{
            Username = 'migration'
            Password = 'Vermeg+123'
            Domain = 'BMCE BANK'
            Type = 'standard'
        }
        Modules = @{
            'MegaCustody' = @{ Url = 'http://10.1.146.163:9082/MegaCustody/login.jsp'; Menu = 'Projects/BMCE/Custody/saisie.txt' }
        }
    }
}

if (-not $projectConfigs.ContainsKey($Project)) {
    throw "Projet non supporte: ${Project}"
}

if ($RunProfile -eq 'ProcessRL' -and $Project -notin @('CDG', 'AWB')) {
    throw "RunProfile ProcessRL est supporte uniquement pour les projets CDG et AWB"
}

$config = $projectConfigs[$Project]
if (-not $config.Modules.ContainsKey($Module)) {
    $available = ($config.Modules.Keys | Sort-Object) -join ', '
    throw "Module non supporte pour ${Project}: ${Module}. Modules disponibles: ${available}"
}

$moduleConfig = $config.Modules[$Module]
$authConfig = if ($moduleConfig.ContainsKey('Auth')) { $moduleConfig.Auth } else { $config.Auth }
$scriptFile = $config.Script
if ($RunProfile -eq 'ProcessRL') {
    if ($Project -eq 'CDG') {
        $scriptFile = 'Process_RL_CDG.py'
    } elseif ($Project -eq 'AWB') {
        $scriptFile = 'Process_RL_AWB.py'
    }
}

$scriptPath = Join-Path $workspace $scriptFile
if (-not (Test-Path $scriptPath)) {
    throw "Script introuvable: $scriptPath"
}

if ([string]::IsNullOrWhiteSpace($MenuPathFile)) {
    if ($RunProfile -eq 'ProcessRL') {
        if ($Project -eq 'CDG') {
            $MenuPathFile = 'Projects/CDG/Custody menu/process_rl.txt'
        } elseif ($Project -eq 'AWB') {
            $MenuPathFile = 'Projects/AWB/custody/process_rl.txt'
        } else {
            $MenuPathFile = $moduleConfig.Menu
        }
    } else {
        $MenuPathFile = $moduleConfig.Menu
    }
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

$variablesDir = Join-Path $workspace 'variable_saisies'
$preferredCreationRoleEntiteVariablesFile = Join-Path $variablesDir 'Creationu_role_entite.txt'
$creationRoleEntiteVariablesFile = Join-Path $variablesDir 'creation_role_entité.txt'
if (Test-Path $preferredCreationRoleEntiteVariablesFile) {
    $creationRoleEntiteVariablesFile = $preferredCreationRoleEntiteVariablesFile
}
if (-not (Test-Path $creationRoleEntiteVariablesFile)) {
    $candidate = Get-ChildItem -Path $variablesDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '(?i)role[_\s-]*entit' } |
        Sort-Object -Property LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -ne $candidate) {
        $creationRoleEntiteVariablesFile = $candidate.FullName
    }
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
$env:CREATION_ROLE_ENTITE_VARIABLES_FILE = $creationRoleEntiteVariablesFile
if ($projectConfigs[$Project].Modules.ContainsKey('MegaCommon')) {
    $env:MEGACOMMON_URL = $projectConfigs[$Project].Modules['MegaCommon'].Url
}
if ($Project -eq 'AWB' -and $RunProfile -eq 'ProcessRL') {
    $env:AWB_PROCESS_RL_VARIABLES_FILE = Join-Path $workspace 'variable_saisies/Instruction_Client_awb.txt'
}

# Set project-specific saisie variables file
if ($Project -eq 'CDG') {
    $saisieVariablesFile = Join-Path $variablesDir 'Instruction_Client_CDG.txt'
    $env:SAISIE_INSTRUCTION_CLIENT_VARIABLES_FILE = $saisieVariablesFile
}
if ($Project -eq 'BMCE') {
    $saisieVariablesFile = Join-Path $variablesDir 'Instruction_Client_BMCE.txt'
    $env:SAISIE_VARIABLES_FILE = $saisieVariablesFile
}

Write-Host "Project          : $Project"
Write-Host "Module           : $Module"
Write-Host "RunProfile       : $RunProfile"
Write-Host "Script           : $scriptPath"
Write-Host "MENU_PATH_FILE   : $env:MENU_PATH_FILE"
Write-Host "PROJECT_SLUG     : $env:PROJECT_SLUG"
Write-Host "MENU_CATEGORY_SLUG: $env:MENU_CATEGORY_SLUG"
Write-Host "SCREENSHOT_DIR   : $env:SCREENSHOT_DIR"
Write-Host "MODULE_URL       : $env:MODULE_URL"
Write-Host "AUTH_USERNAME    : $env:AUTH_USERNAME"
Write-Host "AUTH_DOMAIN      : $env:AUTH_DOMAIN"
Write-Host "AUTH_TYPE        : $env:AUTH_TYPE"
Write-Host "CREATION_ROLE_ENTITE_VARIABLES_FILE: $env:CREATION_ROLE_ENTITE_VARIABLES_FILE"

if ($DryRun) {
    Write-Host 'DryRun active: execution ignoree.'
    return
}

Push-Location "$workspace"
try {
    & "$pythonExe" "$scriptPath"
} finally {
    Pop-Location
}
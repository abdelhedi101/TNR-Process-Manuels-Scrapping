param(
    # Liste des modules a enchainer (par defaut: les 8 modules BMCE).
    [string[]]$Modules = @(
        'MegaCommon',
        'MegaCor',
        'MegaCustody',
        'MegaLend',
        'MegaTrade',
        'MegaAccounting',
        'MegaCompliance',
        'MegaIssuer'
    ),

    [string]$ScreenshotDir = 'screenshots',

    # Utilise les fichiers menu "_complet.txt" quand ils existent.
    [switch]$Complet,

    # Test a blanc: affiche la config sans lancer Chrome.
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$launcher = Join-Path $PSScriptRoot 'launch_non_regression.ps1'
if (-not (Test-Path $launcher)) {
    throw "Lanceur introuvable: $launcher"
}

$workspace = Split-Path -Parent $PSScriptRoot

# Fichiers menu "_complet.txt" disponibles par module (sinon defaut du lanceur).
$completMenus = @{
    'MegaCommon'     = 'Projects/BMCE/Common/bmce_common_complet.txt'
    'MegaCor'        = 'Projects/BMCE/Cor/bmce_core_complet.txt'
    'MegaCustody'    = 'Projects/BMCE/Custody/bmce_custody_complet.txt'
    'MegaLend'       = 'Projects/BMCE/MegaLend/bmce_lend_complet.txt'
    'MegaCompliance' = 'Projects/BMCE/Compliance/bmce_compliance_complet.txt'
}

$results = @()

foreach ($module in $Modules) {
    Write-Host "`n===== Lancement BMCE / $module =====" -ForegroundColor Cyan

    # Construit les arguments transmis au lanceur.
    $params = @{
        Project       = 'BMCE'
        Module        = $module
        ScreenshotDir = $ScreenshotDir
    }
    if ($DryRun) {
        $params['DryRun'] = $true
    }
    if ($Complet -and $completMenus.ContainsKey($module)) {
        $menuPath = $completMenus[$module]
        if (Test-Path (Join-Path $workspace $menuPath)) {
            $params['MenuPathFile'] = $menuPath
            Write-Host "Menu complet      : $menuPath" -ForegroundColor DarkGray
        } else {
            Write-Host "Menu complet introuvable, defaut utilise pour $module" -ForegroundColor Yellow
        }
    }

    try {
        & $launcher @params
        $results += [pscustomobject]@{ Module = $module; Status = 'OK' }
    } catch {
        Write-Host "ECHEC sur $module : $($_.Exception.Message)" -ForegroundColor Red
        $results += [pscustomobject]@{ Module = $module; Status = "ECHEC: $($_.Exception.Message)" }
    }
}

Write-Host "`n===== Recapitulatif =====" -ForegroundColor Green
$results | Format-Table -AutoSize

$failed = @($results | Where-Object { $_.Status -ne 'OK' })
if ($failed.Count -gt 0) {
    Write-Host "$($failed.Count)/$($results.Count) module(s) en echec." -ForegroundColor Red
    exit 1
}
Write-Host "Tous les modules ($($results.Count)) ont ete traites." -ForegroundColor Green

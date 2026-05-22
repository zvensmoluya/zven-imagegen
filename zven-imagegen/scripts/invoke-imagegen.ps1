$ErrorActionPreference = 'Stop'

$ForwardArgs = $args

function Get-CodexHome {
    if ($env:CODEX_HOME) {
        return $env:CODEX_HOME
    }
    return Join-Path $HOME '.codex'
}

function Get-ConfigBaseUrl {
    param([string] $CodexHome)

    $configPath = Join-Path $CodexHome 'config.toml'
    if (-not (Test-Path -LiteralPath $configPath)) {
        return $null
    }

    $content = Get-Content -Raw -LiteralPath $configPath
    $match = [regex]::Match($content, '(?m)^\s*base_url\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
        return $null
    }

    return $match.Groups[1].Value
}

function Get-AuthApiKey {
    param([string] $CodexHome)

    $authPath = Join-Path $CodexHome 'auth.json'
    if (-not (Test-Path -LiteralPath $authPath)) {
        return $null
    }

    $auth = Get-Content -Raw -LiteralPath $authPath | ConvertFrom-Json
    if ($auth.PSObject.Properties.Name -contains 'OPENAI_API_KEY') {
        return $auth.OPENAI_API_KEY
    }

    return $null
}

function Find-ProjectEnvFile {
    $names = @('.agentonlyenv', '.imagegen.env', '.env.imagegen')
    $dir = (Get-Location).Path

    while ($dir) {
        foreach ($name in $names) {
            $candidate = Join-Path $dir $name
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }

        $parent = Split-Path -Parent $dir
        if (-not $parent -or $parent -eq $dir) {
            break
        }
        $dir = $parent
    }

    return $null
}

function Find-RepoStreamHelper {
    $dir = (Get-Location).Path

    while ($dir) {
        $candidate = Join-Path $dir 'scripts\imagegen_stream.py'
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }

        $parent = Split-Path -Parent $dir
        if (-not $parent -or $parent -eq $dir) {
            break
        }
        $dir = $parent
    }

    return $null
}

function Find-SkillStreamHelper {
    $scriptPath = $PSCommandPath
    if (-not $scriptPath) {
        return $null
    }

    $scriptDir = Split-Path -Parent $scriptPath
    $candidate = Join-Path $scriptDir 'imagegen_stream.py'
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    return $null
}

function Find-RepoPython {
    $dir = (Get-Location).Path

    while ($dir) {
        $candidates = @(
            (Join-Path $dir '.venv\Scripts\python.exe'),
            (Join-Path $dir '.venv\bin\python')
        )

        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }

        $parent = Split-Path -Parent $dir
        if (-not $parent -or $parent -eq $dir) {
            break
        }
        $dir = $parent
    }

    return 'python'
}

function Read-DotEnvValue {
    param(
        [string] $Path,
        [string[]] $Names
    )

    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        $match = [regex]::Match($trimmed, '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
        if (-not $match.Success) {
            continue
        }

        $name = $match.Groups[1].Value
        if ($Names -notcontains $name) {
            continue
        }

        $value = $match.Groups[2].Value.Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        return $value
    }

    return $null
}

function Normalize-BaseUrl {
    param([string] $BaseUrl)

    if (-not $BaseUrl) {
        return $null
    }

    $trimmed = $BaseUrl.Trim().TrimEnd('/')
    if ($trimmed -match '/v1$') {
        return $trimmed
    }

    return "$trimmed/v1"
}

function Test-CanUseRepoStreamHelper {
    param([object[]] $ForwardedArgs)

    if (-not $ForwardedArgs -or $ForwardedArgs.Count -eq 0) {
        return $false
    }

    if (@('generate', 'edit', 'generate-batch') -notcontains $ForwardedArgs[0]) {
        return $false
    }

    $unsupported = @(
        '--augment',
        '--no-augment',
        '--use-case',
        '--scene',
        '--subject',
        '--style',
        '--composition',
        '--lighting',
        '--palette',
        '--materials',
        '--text',
        '--constraints',
        '--negative',
        '--downscale-max-dim',
        '--downscale-suffix',
        '--concurrency',
        '--max-attempts'
    )

    foreach ($arg in $ForwardedArgs) {
        $name = ($arg -split '=', 2)[0]
        if ($unsupported -contains $name) {
            return $false
        }
    }

    return $true
}

$codexHome = Get-CodexHome
$imageGenScriptCandidates = @(
    (Join-Path $codexHome 'skills\imagegen\scripts\image_gen.py'),
    (Join-Path $codexHome 'skills\.system\imagegen\scripts\image_gen.py')
)
$imageGenScript = $imageGenScriptCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$repoStreamHelper = Find-RepoStreamHelper
$skillStreamHelper = Find-SkillStreamHelper
$streamHelper = $repoStreamHelper
if (-not $streamHelper) {
    $streamHelper = $skillStreamHelper
}
$pythonExe = Find-RepoPython
$projectEnvFile = Find-ProjectEnvFile

if (-not $imageGenScript -and -not $streamHelper) {
    throw "No image generation helper found. Checked stream helper next to this wrapper and: $($imageGenScriptCandidates -join ', ')"
}

$apiKey = $env:IMAGEGEN_OPENAI_API_KEY
if (-not $apiKey) {
    $apiKey = Read-DotEnvValue -Path $projectEnvFile -Names @('IMAGEGEN_OPENAI_API_KEY')
}
if (-not $apiKey) {
    $apiKey = Get-AuthApiKey -CodexHome $codexHome
}

$baseUrl = $env:IMAGEGEN_OPENAI_BASE_URL
if (-not $baseUrl) {
    $baseUrl = Read-DotEnvValue -Path $projectEnvFile -Names @('IMAGEGEN_OPENAI_BASE_URL')
}
if (-not $baseUrl) {
    $baseUrl = Get-ConfigBaseUrl -CodexHome $codexHome
}
$baseUrl = Normalize-BaseUrl -BaseUrl $baseUrl

if (-not $apiKey) {
    throw "No image API key found. Set IMAGEGEN_OPENAI_API_KEY, or provide OPENAI_API_KEY in Codex auth.json."
}

if (-not $baseUrl) {
    throw "No image base URL found. Set IMAGEGEN_OPENAI_BASE_URL, or configure base_url in Codex config.toml."
}

$env:OPENAI_API_KEY = $apiKey
$env:OPENAI_BASE_URL = $baseUrl
$env:IMAGEGEN_OPENAI_API_KEY = $apiKey
$env:IMAGEGEN_OPENAI_BASE_URL = $baseUrl

if ($streamHelper -and (Test-CanUseRepoStreamHelper -ForwardedArgs $ForwardArgs)) {
    & $pythonExe $streamHelper @ForwardArgs
    exit $LASTEXITCODE
}

& $pythonExe $imageGenScript @ForwardArgs
exit $LASTEXITCODE

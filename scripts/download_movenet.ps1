param(
    [string]$Destination = ''
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $Destination) {
    $Destination = Join-Path $repositoryRoot 'models/movenet_lightning.tflite'
} elseif (-not [System.IO.Path]::IsPathRooted($Destination)) {
    $Destination = Join-Path $repositoryRoot $Destination
}

$url = 'https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite'
$expectedSha256 = '0fac2226112d0371903ca86e3853cec24ef603a0b2f96f589b180f0ebdd135ab'
$destinationDirectory = Split-Path -Parent $Destination
New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null

if (Test-Path -LiteralPath $Destination) {
    $existing = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($existing -eq $expectedSha256) {
        Write-Output "MoveNet Lightning float16 v4 is already verified: $Destination"
        exit 0
    }
    throw "A different model already exists at '$Destination'. Keep it or choose another destination; it was not overwritten."
}

$temporaryPath = "$Destination.$([guid]::NewGuid().ToString('N')).download"
try {
    Invoke-WebRequest -Uri $url -OutFile $temporaryPath
    $actualSha256 = (Get-FileHash -LiteralPath $temporaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256) {
        throw "Downloaded model failed SHA-256 verification. Expected $expectedSha256; got $actualSha256."
    }
    Move-Item -LiteralPath $temporaryPath -Destination $Destination
    Write-Output "Verified MoveNet Lightning float16 v4: $Destination"
} finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}

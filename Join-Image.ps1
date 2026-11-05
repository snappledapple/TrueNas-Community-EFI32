[CmdletBinding()]
param([string]$Manifest = (Join-Path $PSScriptRoot 'download-manifest.json'))
$ErrorActionPreference = 'Stop'
$manifestPath = (Resolve-Path -LiteralPath $Manifest).Path
$base = Split-Path -Parent $manifestPath
$info = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
function Assert-FileName([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name) -or [IO.Path]::GetFileName($Name) -ne $Name -or
        $Name -match '[\\/:]' -or $Name -in @('.', '..')) { throw 'Invalid manifest filename' }
}
Assert-FileName $info.image
$target = Join-Path $base $info.image
if (Test-Path -LiteralPath $target) { throw "Output already exists: $target" }
foreach ($part in $info.parts) {
    Assert-FileName $part.file
    $path = Join-Path $base $part.file
    $item = Get-Item -LiteralPath $path
    if ($item.PSIsContainer -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Regular part files required' }
    if ($item.Length -ne $part.bytes -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $part.sha256) {
        throw "Part verification failed: $($part.file)"
    }
}
$stream = $null
$created = $false
try {
    $stream = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $created = $true
    foreach ($part in $info.parts) {
        $inputStream = [IO.File]::OpenRead((Join-Path $base $part.file))
        try { $inputStream.CopyTo($stream, 8MB) } finally { $inputStream.Dispose() }
    }
    $stream.Flush($true)
    $stream.Dispose()
    $stream = $null
    if ((Get-Item -LiteralPath $target).Length -ne $info.bytes -or
        (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $info.sha256) {
        throw 'Final image verification failed'
    }
} catch {
    if ($stream) { $stream.Dispose() }
    if ($created -and (Test-Path -LiteralPath $target)) { Remove-Item -LiteralPath $target -Force }
    throw
}
Write-Output "Verified image ready for Rufus DD mode or balenaEtcher: $target"

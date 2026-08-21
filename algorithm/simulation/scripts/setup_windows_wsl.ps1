#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

$wslExe = Join-Path $env:WINDIR 'System32\wsl.exe'

# An empty WSL installation writes "no distributions installed" to stderr.
# Query through cmd and discard only that diagnostic so Windows PowerShell 5.1
# does not turn the normal first-install state into a NativeCommandError.
$installedOutput = & $env:ComSpec /d /c 'wsl.exe --list --quiet 2>nul'
$installed = @(
    $installedOutput |
        ForEach-Object { ([string]$_ -replace "`0", '').Trim() } |
        Where-Object { $_ }
)

if ($installed -contains 'Ubuntu-22.04') {
    Write-Host 'Ubuntu-22.04 is already installed.'
    $setVersion = Start-Process -FilePath $wslExe `
        -ArgumentList @('--set-version', 'Ubuntu-22.04', '2') `
        -Wait -PassThru -NoNewWindow
    if ($setVersion.ExitCode -ne 0) {
        throw "Could not set Ubuntu-22.04 to WSL2 (exit code $($setVersion.ExitCode))."
    }
    exit 0
}

Write-Host 'Installing Ubuntu 22.04 for the ROS 2 Humble simulation environment...'
$install = Start-Process -FilePath $wslExe `
    -ArgumentList @('--install', '--distribution', 'Ubuntu-22.04') `
    -Wait -PassThru -NoNewWindow

if ($install.ExitCode -ne 0) {
    throw "WSL installation failed (exit code $($install.ExitCode)). Run 'wsl --install -d Ubuntu-22.04' directly in this Administrator PowerShell and send back its complete output."
}

Write-Host ''
Write-Host 'WSL/Ubuntu installation command completed.'
Write-Host 'Restart Windows if requested. Then open Ubuntu 22.04 once and create its Linux user.'

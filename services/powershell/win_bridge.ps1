# win_bridge.ps1 — JSON-RPC через stdin/stdout для JArbis (Windows-специфика)
# Вход:  {"method":"ping"}  или  {"method":"list_audio_outputs"}
# Выход: JSON одной строкой

$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [Text.UTF8Encoding]::UTF8
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

function Write-Json($obj) {
    $json = $obj | ConvertTo-Json -Compress -Depth 6
    [Console]::Out.WriteLine($json)
}

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) {
        Write-Json @{ ok = $false; error = "empty input" }
        exit 1
    }
    $req = $raw | ConvertFrom-Json
    $method = [string]$req.method

    if ($method -eq "ping") {
        Write-Json @{ ok = $true; backend = "powershell"; version = "1.0" }
        exit 0
    }

    if ($method -eq "list_start_apps") {
        [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8
        $OutputEncoding = [Text.UTF8Encoding]::UTF8
        chcp 65001 | Out-Null
        $apps = @()
        Get-StartApps | Where-Object { $_.Name -ne "" } | ForEach-Object {
            $apps += @{
                name  = [string]$_.Name
                appId = [string]$_.AppID
            }
        }
        Write-Json @{ ok = $true; apps = $apps; count = $apps.Count }
        exit 0
    }

    if ($method -eq "list_audio_outputs") {
        $list = @(@{ id = ""; label = "По умолчанию" })
        try {
            Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4CB6-91AE-5E9AF7A6A27C"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator { int f(); int GetDefaultAudioEndpoint(int dataFlow, int role, out object dev); }
"@ -ErrorAction SilentlyContinue | Out-Null
        } catch {}
        # Fallback: имена через WMI
        Get-CimInstance Win32_SoundDevice -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.Name) {
                $list += @{ id = $_.Name; label = $_.Name }
            }
        }
        Write-Json @{ ok = $true; devices = $list }
        exit 0
    }

    if ($method -eq "uwp_app_count") {
        $count = 0
        try {
            $count = (Get-AppxPackage -ErrorAction SilentlyContinue | Measure-Object).Count
        } catch {}
        Write-Json @{ ok = $true; count = $count }
        exit 0
    }

    Write-Json @{ ok = $false; error = "unknown method: $method" }
    exit 1
} catch {
    Write-Json @{ ok = $false; error = $_.Exception.Message }
    exit 1
}

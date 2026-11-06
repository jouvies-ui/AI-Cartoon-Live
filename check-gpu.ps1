param([string]$Report = "")
$ErrorActionPreference = 'Stop'
$result = @{ok=$false; adapters=@(); reason='需要 NVIDIA GTX 10 系列或更新显卡，并安装 NVIDIA 驱动。'}
try {
    $adapters = @(Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' })
    $result.adapters = @($adapters | ForEach-Object { @{name=$_.Name; driver=$_.DriverVersion; error=$_.ConfigManagerErrorCode} })
    $smi = @("$env:WINDIR\System32\nvidia-smi.exe", "$env:WINDIR\Sysnative\nvidia-smi.exe", "$env:ProgramFiles\NVIDIA Corporation\NVSMI\nvidia-smi.exe")
    $found = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($found) { $smi += $found.Source }
    foreach ($exe in ($smi | Select-Object -Unique)) {
        if (!(Test-Path $exe)) { continue }
        $rows = & $exe --query-gpu=name,compute_cap --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0) {
            foreach ($row in $rows) {
                $parts = $row -split ','
                $cap = 0.0
                if ([double]::TryParse($parts[-1].Trim(), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$cap) -and $cap -ge 6.1) {
                    $result.ok=$true; $result.reason='NVIDIA 显卡检查通过'; break
                }
            }
        }
    }
    # Older drivers may not expose compute_cap. Keep a narrow generation allowlist.
    if (!$result.ok) {
        foreach ($adapter in $adapters) {
            if ($adapter.ConfigManagerErrorCode -eq 0 -and $adapter.DriverVersion -and
                $adapter.Name -match '(?i)\bGTX?\s*(10\d{2}|16\d{2})\b|\bRTX\s*(?:[2-9]\d{3}|[1-9]\d{4})\b|\bRTX\s*[AB]\d{3,4}\b') {
                $result.ok=$true; $result.reason='NVIDIA 显卡检查通过'
            }
        }
    }
} catch { $result.reason='无法确认显卡和驱动，请安装 NVIDIA 驱动后重新运行安装程序。' }
if ($Report) { $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Report -Encoding UTF8 }
if ($result.ok) { exit 0 } else { exit 10 }

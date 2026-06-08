# Attempt 3 — Binary-patched DSDT via acpitables registry + ACPIOVERRIDETEST BCD flag
# Loads dsdt_patched.aml (DSDT with SPSS _DEP byte-patched to GLNK) into the
# acpitables registry key. On ARM64 / Insyde H2O V1.09 this path is silently
# ignored by the firmware. Kept as a historical artifact showing exactly what was run.

$aml = [System.IO.File]::ReadAllBytes("C:\Drivers\dsdt_patched.aml")
$regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\acpitables"
if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
New-ItemProperty -Path $regPath -Name "00000000" -Value $aml -PropertyType Binary -Force | Out-Null
Write-Output "DSDT loaded: $($aml.Length) bytes"
$stored = (Get-ItemProperty -Path $regPath).'00000000'
$sig = [System.Text.Encoding]::ASCII.GetString($stored[0..3])
$oemid = [System.Text.Encoding]::ASCII.GetString($stored[10..15])
$tableid = [System.Text.Encoding]::ASCII.GetString($stored[16..23])
Write-Output "Stored: sig=$sig OEM=$oemid Table=$tableid size=$($stored.Length)"
bcdedit /set "{current}" loadoptions ACPIOVERRIDETEST
Write-Output "BCD loadoptions set"
bcdedit /enum "{current}" | Where-Object { $_ -match 'loadoptions|description' }
"Done" | Out-File "C:\Drivers\inject_result.txt"

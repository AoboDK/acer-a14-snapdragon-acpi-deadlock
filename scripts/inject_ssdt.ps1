# Attempt 1 — SSDT via acpitables registry + ACPIOVERRIDETEST BCD flag
# Loads ssdt_qcsp.aml (stub QCSP device, no _DEP) into
# HKLM\SYSTEM\CurrentControlSet\Control\acpitables as value "00000000".
# On ARM64 / Insyde H2O V1.09 this path is silently ignored by the firmware.
# Kept as a historical artifact showing exactly what was run.

$aml = [System.IO.File]::ReadAllBytes("C:\Drivers\ssdt_qcsp.aml")
$regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\acpitables"
if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
New-ItemProperty -Path $regPath -Name "00000000" -Value $aml -PropertyType Binary -Force | Out-Null
$check = (Get-ItemProperty $regPath).'00000000'
$result = if ($check.Length -eq $aml.Length) { "SUCCESS: $($check.Length) bytes written" } else { "FAILED: expected $($aml.Length) got $($check.Length)" }
$result | Out-File -FilePath "C:\Drivers\ssdt_inject_result.txt" -Encoding UTF8
[System.Windows.Forms.MessageBox]::Show($result, "SSDT Injection") | Out-Null

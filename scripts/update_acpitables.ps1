# Canary test script for Attempts 1 and 3
# Loads ssdt_test.aml (stub device with HID "QCOM1234", no _DEP) into the
# acpitables registry key to verify the write mechanism works before committing
# to the real QCSP fix SSDT or patched DSDT. See also: efi-injection/ssdt_test.asl

$testAml = [System.IO.File]::ReadAllBytes("C:\Drivers\ssdt_test.aml")
$regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\acpitables"
New-Item -Path $regPath -Force | Out-Null
New-ItemProperty -Path $regPath -Name "00000000" -Value $testAml -PropertyType Binary -Force | Out-Null
$val = (Get-ItemProperty $regPath)."00000000"
$tbl = [System.Text.Encoding]::ASCII.GetString($val[16..23])
"Registry updated: $($val.Length) bytes, Table: $tbl" | Out-File "C:\Drivers\reg_update_result.txt"

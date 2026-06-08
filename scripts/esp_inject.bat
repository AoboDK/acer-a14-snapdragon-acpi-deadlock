@echo off
REM Attempt 2 — SSDT placed in candidate ESP paths for Insyde firmware auto-load
REM Mounts the EFI System Partition to S:, copies ssdt_qcsp.aml to every candidate
REM path documented for SSDT auto-load (EFI\ACPI\, EFI\OEM\, acpi\, root).
REM On Insyde H2O V1.09 none of these paths are read by the firmware.
REM Kept as a historical artifact showing exactly what was run.

mountvol S: /s

mkdir S:\EFI\ACPI\ 2>nul
mkdir S:\EFI\OEM\ 2>nul
mkdir S:\acpi\ 2>nul

copy /Y C:\Drivers\ssdt_qcsp.aml S:\EFI\ACPI\ssdt_qcsp.aml
copy /Y C:\Drivers\ssdt_qcsp.aml S:\EFI\OEM\ssdt_qcsp.aml
copy /Y C:\Drivers\ssdt_qcsp.aml S:\acpi\ssdt_qcsp.aml
copy /Y C:\Drivers\ssdt_qcsp.aml S:\ssdt_qcsp.aml

echo Full ESP tree: > C:\Drivers\esp_inject_result.txt
tree S:\ /F >> C:\Drivers\esp_inject_result.txt

echo Done. See C:\Drivers\esp_inject_result.txt

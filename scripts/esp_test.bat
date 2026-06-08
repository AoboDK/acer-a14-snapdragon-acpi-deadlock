@echo off
REM Canary pre-test for Attempt 2
REM Same as esp_inject.bat but uses ssdt_test.aml (HID "QCOM1234") to verify
REM the ESP write mechanism works before deploying the real QCSP fix SSDT.
REM See also: efi-injection/ssdt_test.asl

mountvol S: /s

mkdir S:\EFI\ACPI\ 2>nul
mkdir S:\EFI\OEM\ 2>nul
mkdir S:\acpi\ 2>nul

copy /Y C:\Drivers\ssdt_test.aml S:\EFI\ACPI\ssdt_test.aml
copy /Y C:\Drivers\ssdt_test.aml S:\EFI\OEM\ssdt_test.aml
copy /Y C:\Drivers\ssdt_test.aml S:\acpi\ssdt_test.aml
copy /Y C:\Drivers\ssdt_test.aml S:\ssdt_test.aml

echo Full ESP tree: > C:\Drivers\esp_test_result.txt
tree S:\ /F >> C:\Drivers\esp_test_result.txt

echo Done. See C:\Drivers\esp_test_result.txt

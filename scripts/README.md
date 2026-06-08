# scripts/ — Injection methodology artifacts

These are the exact scripts run during the ACPI injection investigation. They are
preserved verbatim (including hardcoded `C:\Drivers\` paths) as a reproducible
record of what was attempted. Each script corresponds to a numbered attempt in
[`docs/ATTEMPTS.md`](../docs/ATTEMPTS.md) and [`docs/EFI_Injection_Tracking.md`](../docs/EFI_Injection_Tracking.md).

| Script | Attempt | Method | Result |
|---|---|---|---|
| `update_acpitables.ps1` | Canary pre-test (1 & 3) | Load `ssdt_test.aml` (HID `QCOM1234`) via `acpitables` registry | Registry write succeeds; Windows ARM64 ignores it |
| `inject_ssdt.ps1` | Attempt 1 | Load `ssdt_qcsp.aml` (stub QCSP, no `_DEP`) via `acpitables` + `ACPIOVERRIDETEST` BCD flag | Registry write succeeds; ARM64 UEFI ignores registry-based ACPI override |
| `esp_test.bat` | Canary pre-test (2) | Copy `ssdt_test.aml` to candidate ESP paths | Files placed successfully; firmware does not load them |
| `esp_inject.bat` | Attempt 2 | Copy `ssdt_qcsp.aml` to `S:\EFI\ACPI\`, `S:\EFI\OEM\`, `S:\acpi\`, `S:\` | Files placed successfully; Insyde H2O V1.09 does not load SSDT files from ESP |
| `inject_dsdt.ps1` | Attempt 3 | Load binary-patched `dsdt_patched.aml` via `acpitables` + `ACPIOVERRIDETEST` BCD flag | Same ARM64 ignore; DSDT override mechanism is x86/BIOS-only |

The canary SSDT source is at [`efi-injection/ssdt_test.asl`](../efi-injection/ssdt_test.asl).
The real QCSP fix SSDT source is at [`efi-injection/ssdt_qcsp.asl`](../efi-injection/ssdt_qcsp.asl).

For the UEFI injection attempts (5a–5l) that used `AcpiInject.efi`, see
[`efi-injection/`](../efi-injection/) and [`docs/EFI_Injection_Tracking.md`](../docs/EFI_Injection_Tracking.md).

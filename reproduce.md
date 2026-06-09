# Minimum Reproducible Test Case

This document describes the minimum steps to reproduce the QCSP/SPSS circular
dependency deadlock on the Acer A14-11M and verify the broken state with exact
PowerShell commands.

---

## Hardware

| Field | Value |
|---|---|
| Model | Acer Swift 14 AI A14-11M |
| Product code | NX.JP3ED.002 |
| SoC | Qualcomm Snapdragon X 8380 (SUBSYS_CRD08380) |
| Firmware | Insyde H2O V1.09 |
| OS | Windows 11 ARM64 26H1, Build 26200 |

> This deadlock has been observed on NX.JP3ED.002 with firmware V1.09. It may
> apply to other Snapdragon X 8380 CRD-class boards; if you observe this on a
> different SKU, please open an issue.

---

## Setup — how to reach the broken state

The broken state arises from a clean Windows 11 ARM64 reinstall. The factory
OS on this device was wiped by the built-in Windows "Reset this PC" function,
which left the machine unbootable (hung at Acer logo). The only available
recovery path was a fresh install from a Microsoft ISO.

**Install procedure (FAT32-USB + split-WIM method):**

1. Download the official Windows 11 ARM64 ISO from Microsoft.
2. Format a USB drive as FAT32.
3. Mount the ISO and copy all files to the USB **except** `sources\install.wim`
   (too large for FAT32).
4. Split `install.wim` into 3.8 GB parts:
   ```cmd
   Dism /Split-Image /ImageFile:D:\sources\install.wim /SWMFile:E:\sources\install.swm /FileSize:3800
   ```
5. Copy the resulting `.swm` parts to `E:\sources\` on the USB.
6. Boot from the USB using a **USB-C port** (USB-A produces a "missing drivers"
   error on this device and cannot complete the install).
7. Complete the Windows installer. Do not install any drivers yet.

After install, the broken device state described below is present before any
driver installation.

---

## Expected broken state

After a clean reinstall with no driver installation, the following conditions hold:

| Signal | Expected observation |
|---|---|
| `ACPI\QCOM0C87` (QCSP) | **Absent** — not in PnP tree at all |
| `ACPI\QCOM0C8D` (SPSS) | Present, failing with `CM_PROB_FAILED_ADD` |
| PIL TZ `Linked` value | Blank or absent |
| ADSP / CDSP | `CM_PROB_FAILED_ADD` |
| Bluetooth radio | Not enumerated |
| Audio | Not functional |

After safe single-INF driver installation (see [`paper.md §3–§4`](paper.md)),
roughly 60% of the platform stack recovers, but the core deadlock signals
(QCSP absent, SPSS failing, PIL TZ not linked) persist unchanged.

---

## Verification commands

Run all commands in an elevated PowerShell 7 (`pwsh`) prompt.

### 1 — List all failing devices

```powershell
Get-PnpDevice |
    Where-Object { $_.Status -ne "OK" } |
    Where-Object { $_.InstanceId -notlike "SWD\MSRRAS*" } |
    Select-Object Class, FriendlyName, Status, Problem, InstanceId |
    Format-Table -AutoSize
```

**Expected:** SPSS (`ACPI\QCOM0C8D`), ADSP (`ACPI\QCOM0C1B`), CDSP (`ACPI\QCOM0CB0`),
and approximately 17 QCPEP thermal/policy devices are present and failing. QCSP
(`ACPI\QCOM0C87`) does **not** appear in this list — it is not enumerated at all.

---

### 2 — Confirm QCSP is absent from the PnP tree

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*QCOM0C87*" }
```

**Expected:** No output. `QCOM0C87` is not present in the PnP manager.

---

### 3 — Confirm SPSS is present and failing

```powershell
Get-PnpDevice | Where-Object { $_.InstanceId -like "*QCOM0C8D*" } |
    Select-Object FriendlyName, Status, Problem, InstanceId
```

**Expected:** One row — SPSS present, `Status = Error`, `Problem = CM_PROB_FAILED_ADD`.

---

### 4 — Get detailed SPSS problem status

```powershell
Get-PnpDeviceProperty -InstanceId "ACPI\QCOM0C8D\2&daba3ff&0" `
    -KeyName DEVPKEY_Device_ProblemCode, DEVPKEY_Device_ProblemStatus,
             DEVPKEY_Device_DependencyDependents |
    Select-Object KeyName, Data
```

**Expected:**
- `ProblemCode` = 31 (`CM_PROB_FAILED_ADD`)
- `ProblemStatus` = `0xC000003B` (`STATUS_OBJECT_NAME_NOT_FOUND` /
  `STATUS_OBJECT_PATH_COMPONENT_NOT_A_DIRECTORY`)
- `DependencyDependents` = `\_SB.QCSP` (ACPI namespace path format — indicates
  QCSP was registered as a dependent but never presented to PnP)

> The `InstanceId` suffix may vary. Use `Get-PnpDevice | Where-Object {
> $_.InstanceId -like "*QCOM0C8D*" }` first to confirm the exact ID on your system.

---

### 5 — Check PIL TZ interface link state

```powershell
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
$base = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid"
Get-ChildItem $base -Recurse -ErrorAction SilentlyContinue |
    Get-ItemProperty -ErrorAction SilentlyContinue |
    Select-Object PSPath, Linked
```

**Expected:** The registry key exists (the interface class is registered) but the
`Linked` value is absent or blank. A value of `Linked=1` would mean `qcsp.sys`
has loaded and activated the interface — that is the target state, not the
broken state.

---

### 6 — Read the DSDT `_DEP` byte oracle

```powershell
$dsdt = (Get-ItemProperty `
    "HKLM:\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000" `
    -Name "00000000").00000000
[System.BitConverter]::ToString($dsdt[0x36C69..0x36C6C])
```

**Expected:** `53-50-53-53` (ASCII "SPSS") — the DSDT `_DEP[2]` reference is
still pointing to SPSS, confirming the deadlock is in the original broken state.
`47-4C-4E-4B` ("GLNK") would indicate a successful patch.

---

### 7 — Export a baseline CSV

```powershell
Get-PnpDevice |
    Where-Object { $_.Status -ne "OK" } |
    Where-Object { $_.InstanceId -notlike "SWD\MSRRAS*" } |
    Select-Object Class, FriendlyName, Status, Problem, InstanceId |
    Export-Csv -Path "$env:USERPROFILE\Desktop\A14\baselines\A14_Baseline_$(Get-Date -Format yyyyMMdd_HHmmss).csv" -NoTypeInformation
```

Use this before and after any driver installation or injection attempt. The diff
between two CSV snapshots is the primary signal for whether a change had any effect.

---

## Summary of expected results — broken state confirmed

| Check | Command | Broken-state result |
|---|---|---|
| QCSP in PnP | Command 2 | No output (absent) |
| SPSS status | Command 3 | Error / CM_PROB_FAILED_ADD |
| SPSS DependencyDependents | Command 4 | `\_SB.QCSP` |
| PIL TZ Linked | Command 5 | Blank or absent |
| DSDT oracle bytes | Command 6 | `53-50-53-53` ("SPSS") |

All five signals present simultaneously = deadlock confirmed and unbroken.
Any injection attempt that breaks the deadlock will show: QCSP present (Command 2),
SPSS started (Command 3), PIL TZ `Linked=1` (Command 5), DSDT oracle `47-4C-4E-4B`
(Command 6 — if the fix was a DSDT patch) or unchanged (Command 6 — if the fix
was an SSDT injection without DSDT modification).

---

## Toolchain required to extend this work

| Tool | Purpose | Source |
|---|---|---|
| PowerShell 7 (`pwsh`) | All diagnostic commands | Built into Windows 11 |
| `pnputil` | Driver staging and install | Built into Windows |
| Python 3 + `keystone-engine` | Building `AcpiInject.efi` | `pip install keystone-engine` |
| `iasl.exe` | ACPI ASL compiler / DSDT disassembly | https://www.acpica.org/downloads |
| FAT32 USB drive | Deploying EFI boot applications | Any |

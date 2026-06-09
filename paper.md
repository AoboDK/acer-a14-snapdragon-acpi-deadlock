# Acer A14-11M Qualcomm ACPI Dependency Deadlock on Windows 11 ARM64

**Status:** Partial recovery documented. Full software fix not yet achieved.
Two UEFI protocol retests (D8a, D8b) pending. Firmware-level remediation
likely required.

---

## Abstract

This paper documents an investigation into Qualcomm platform driver recovery on an
Acer A14-11M (product code NX.JP3ED.002) laptop — Qualcomm Snapdragon X 8380 SoC,
Insyde H2O firmware V1.09, Windows 11 ARM64 build 26200 — after the factory OS was
wiped by the built-in Windows "Reset this PC" function, which left the device
unbootable and forced a clean reinstall from an official Microsoft USB image.

After the clean reinstall, approximately 40 Qualcomm platform devices fail to start.
The root cause is **strongly indicated** to be a circular dependency encoded in the
firmware DSDT: the QCSP device (`_HID = "QCOM0C87"`) carries an `_DEP` reference to
`\_SB.SPSS`; SPSS fails because the PIL TZ interface is not active; PIL TZ is
published by `qcsp.sys`; but `qcsp.sys` cannot load because QCSP is held back by
the unsatisfied `_DEP`. No driver installation can break this loop from within
Windows.

Safe single-INF driver installation restores roughly 60% of the Qualcomm platform
stack. The remaining 40% — ADSP, CDSP, SPSS, the QCPEP thermal/policy cluster,
Adreno GPU, audio, and Bluetooth radio — requires breaking the ACPI deadlock first.

Four standard ACPI override paths and fifteen sub-attempts of a custom UEFI
injection application were exhausted. Every tested in-band ACPI table modification
path from a UEFI boot application has failed on this firmware. Two corrected protocol
retests (D8a: `EFI_ACPI_TABLE_PROTOCOL`; D8b: `EFI_MEMORY_ATTRIBUTE_PROTOCOL`) are
pending and are the last remaining in-band software paths to close.

The evidence for the root-cause model is strong but not vendor-grade proven: several
observations are direct (QCSP absent from PnP, SPSS failing, PIL TZ inactive, DSDT
`_DEP` structure, in-memory `DOE_START_PENDING` flag on SPSS, Windows dependency
database recording `\_SB.QCSP` as SPSS's dependent). The exact Windows ACPI `_DEP`
gate decision has not been directly observed via ETW or kernel debugger — confirmed
as a genuine limitation, not a missed step, after a full-boot WPR trace proved the
relevant providers emit zero events on this system.

---

## 1. Introduction

### 1.1 Hardware under test

| Field | Value |
|---|---|
| Model | Acer Swift 14 AI A14-11M, product code NX.JP3ED.002 |
| SoC | Qualcomm Snapdragon X 8380 (SUBSYS_CRD08380) |
| OS | Windows 11 ARM64 26H1, Build 26200 |
| Firmware | Insyde H2O (QCOMM_/SDM8380_/rev3), V1.09 |
| Firmware status | V1.09 is the latest available for this SKU as of May 2026 |
| Secure Boot | OFF (disabled for driver and UEFI testing) |
| HVCI (Memory Integrity) | ON |

### 1.2 How the device reached this state

The factory Windows install was wiped using the manufacturer-provided
**Settings → System → Recovery → Reset this PC** function. After the reset the
device hung at the Acer boot logo and never reached Windows — the built-in recovery
path was non-functional. The only route back to a working OS was a clean reinstall
from a fresh official Microsoft Windows 11 ARM64 ISO. Every observation in this paper
is from that clean reinstall.

This origin is relevant to the findings: both standard remediation paths
(manufacturer-provided factory reset, Microsoft ISO reinstall) were used, and the
platform-driver deadlock described below is what remained after both.

### 1.3 Install procedure

The reinstall used the FAT32-USB + split-WIM method documented by t0ma5 in
[caccialdo's gist](https://gist.github.com/caccialdo/3b0d0113489ecee456d94c1e9462d755):
split `install.wim` to 3.8 GB `.swm` parts, copy to FAT32 USB, boot from USB-C
(USB-A produces a "missing drivers" error on this device).

---

## 2. Problem Statement

### 2.1 Expected state: broken vs. fixed

| Signal | Broken state (observed) | Fixed state (target) |
|---|---|---|
| `ACPI\QCOM0C87` (QCSP) | Absent from PnP entirely | Present and started |
| `ACPI\QCOM0C8D` (SPSS) | `CM_PROB_FAILED_ADD` | Started |
| PIL TZ `Linked` value | Blank or absent | `Linked=1` |
| ADSP / CDSP | `CM_PROB_FAILED_ADD` | Started |
| Audio / Bluetooth radio / Adreno GPU | Blocked or failing | Restorable |

### 2.2 Failure profile after clean reinstall

After install, `Get-PnpDevice` returns approximately 40 non-OK devices. The principal
failures:

| Hardware ID | Device | Problem |
|---|---|---|
| `ACPI\QCOM0C1B` | ADSP | `CM_PROB_FAILED_ADD` / `0xC0000182` |
| `ACPI\QCOM0CB0` | CDSP | `CM_PROB_FAILED_ADD` / `0xC000003B` |
| `ACPI\QCOM0C8D` | SPSS | `CM_PROB_FAILED_ADD` / `0xC000003B` |
| `ACPI\QCOM0C87` | QCSP | **Absent** — never presented to PnP |
| QCPEP cluster (17 devices) | Thermal / policy | `STATUS_NO_SUCH_DEVICE` |
| `ACPI\VEN_QCOM&DEV_0D17` | Adreno GPU | Failing |
| — | Bluetooth radio | Transport OK; radio not enumerated |
| — | Audio | Blocked by ADSP failure |
| — | Battery reporting | Blocked |

The PIL TZ device interface
(`{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`) is registered in the Windows device
class registry but the `Linked` value is blank rather than `1`.

### 2.3 The `Setup_Driver.cmd` BSOD trap

Acer's bundled `Setup_Driver.cmd` from the 0.7700.1 driver package performs a bulk
recursive install (`pnputil /subdirs /install`). Running this script on a system
already in the broken post-install state triggers a **"SOC critical device removed"
BSOD**. Recovery requires a restore point or full re-image. This script must not be
used on a system in this state. The safe alternative is described in §3.

---

## 3. Methods

### 3.1 Safe single-INF install rule

All driver installations use only:

```powershell
pnputil /add-driver "C:\path\to\driver.inf" /install
```

The `/subdirs` flag is never used. For high-risk platform drivers (`qcpep`, `qcpil`,
`qcsmmu`, `qcsubsys`, `qcscm`): stage-only first (omit `/install`), reboot, export
a baseline CSV and verify no regression, then install in a subsequent step.

### 3.2 Baseline CSV diffing

Before and after each driver phase, a baseline CSV is exported:

```powershell
Get-PnpDevice |
    Where-Object { $_.Status -ne "OK" } |
    Where-Object { $_.InstanceId -notlike "SWD\MSRRAS*" } |
    Select-Object Class, FriendlyName, Status, Problem, InstanceId |
    Export-Csv -Path "$env:USERPROFILE\Desktop\A14\baselines\A14_Baseline_$(Get-Date -Format yyyyMMdd_HHmmss).csv" -NoTypeInformation
```

This diff pair is the primary signal for whether a phase made progress, regressed, or
had no effect.

### 3.3 The PIL TZ oracle

The `Linked` value under the PIL TZ device interface registry key is the definitive
go/no-go signal for any injection attempt:

```powershell
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
$base = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid"
Get-ChildItem $base -Recurse | Get-ItemProperty | Select-Object PSPath, Linked
```

`Linked=1` means `qcsp.sys` has loaded and the deadlock is broken. Blank or absent
means the deadlock persists.

### 3.4 The DSDT byte oracle

Reading bytes `[0x36C69..0x36C6C]` from the live Windows DSDT at
`HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000` gives an unambiguous
signal of patch state:

- `53 50 53 53` ("SPSS") — DSDT is in the original broken state
- `47 4C 4E 4B` ("GLNK") — `_DEP[2]` has been patched; deadlock is broken

### 3.5 DSDT disassembly

The DSDT was extracted from the registry value above and disassembled with `iasl.exe
-d`. This identified the QCSP `_DEP` structure and the exact byte offsets for patching.

### 3.6 Kernel and ETW diagnostics

- **Kernel-PnP static log:** `Microsoft-Windows-Kernel-PnP/Configuration` (732 events)
  and `setupapi.dev.log` — searched for QCSP/SPSS/dependency events.
- **WPR boot trace:** Custom five-provider profile across a full reboot, captured with
  `wpr -stopboot`, analyzed with `tracerpt`.
- **Live kernel debugger:** `bcdedit /debug on` + `kdARM64.exe -kl`; `!devobj`,
  `!devstack`, `!error` on the live SPSS device object; physical-memory `!db`/`!eb`
  on the DSDT pool copy.

---

## 4. Results — Partial Recovery

Safe single-INF driver installation restores the following components to a working
or running state:

| Component | Status after recovery |
|---|---|
| WiFi, Display, Keyboard, Trackpad | Working |
| USB, Card Reader, Camera, NPU | Working |
| PMIC Apps, PMIC GLink | Running |
| TFTP, SCM, GLINK, IPC Router, IPCC, Syscache, SMMU | Running |
| PIL (`qcPILC`), PIL Filter (`qcPILFC`) | Running |
| `qcsubsys` service | Running |

The safe install order validated across 48 sessions:

1. `qcpep` — stage-only, reboot, verify
2. `qcsmmu` — stage-only, reboot, verify
3. `qcscm` — stage-only, reboot, verify
4. `qcPILC` / `qcPILFC` — install, reboot
5. `qcsubsys` — install, reboot
6. PMIC drivers — install, reboot
7. `qcGLINK`, `qcIPCR`, `qcIPCC`, `qcqsap`, `qcTFTP`, `qcsyscache` — install, reboot
8. **ACPI deadlock must be broken before any further subsystem drivers can activate**

Driver sources: Acer OEM package `Base Driver_Qualcomm_0.7700.1_W11ARM64_A` (primary)
and WOA-Project Qualcomm Reference Drivers `8380_CRD/200.0.57.0/`
(https://github.com/WOA-Project/Qualcomm-Reference-Drivers). For the complete
hardware-ID-to-INF mapping, see [`docs/Driver_Reference_Map.md`](docs/Driver_Reference_Map.md).

---

## 5. Root-Cause Model

### 5.1 The circular dependency

The major Qualcomm subsystem cascade traces to a circular dependency in the firmware
DSDT. The DSDT defines the QCSP device as:

```asl
Device (QCSP) {
    Name (_HID, "QCOM0C87")
    Name (_STA, 0x0F)
    Name (_DEP, Package() { \_SB.GLNK, \_SB.SOCP, \_SB.SPSS })
}
```

The deadlock forms in five steps:

```
Step 1: GLNK and SOCP resolve successfully — two of three _DEP entries satisfied.

Step 2: SPSS (ACPI\QCOM0C8D) cannot complete AddDevice.
        Fails with CM_PROB_FAILED_ADD / STATUS_OBJECT_NAME_NOT_FOUND.
        The PIL TZ interface ({E2EB84C1-...}) is not active.

Step 3: PIL TZ is published by qcsp.sys — the driver for QCSP.
        Registry entry exists but Linked is blank.

Step 4: qcsp.sys cannot load — QCSP is never presented to PnP.
        Windows holds back any device whose _DEP is unsatisfied.
        \_SB.SPSS has failed → _DEP not satisfied → QCSP withheld.

Step 5: Loop closes.
        QCSP withheld → qcsp.sys not loaded → PIL TZ not published
        → SPSS AddDevice fails → _DEP on SPSS unsatisfied
        → QCSP withheld → (repeat)
```

No driver installation can break this loop. The relevant INFs (`oem102.inf` and
`oem103.inf` for `qcsp.sys`) are staged and present; the device they match is simply
never presented to the PnP manager.

### 5.2 Diagram

```
QCSP device (ACPI\QCOM0C87)
  _HID = QCOM0C87
  _DEP = { GLNK ✓, SOCP ✓, SPSS ✗ }
        |
        v
Windows withholds QCSP until SPSS is resolved
        |
        v
SPSS (ACPI\QCOM0C8D) fails AddDevice
  Problem: CM_PROB_FAILED_ADD / STATUS_OBJECT_NAME_NOT_FOUND
        |
        v
SPSS requires PIL TZ interface — not active (Linked = blank)
        |
        v
PIL TZ is published by qcsp.sys
        |
        v
qcsp.sys cannot load — QCSP was never presented
        |
        └──────────────────────────────────────┐
                         Circular dependency deadlock
```

### 5.3 The failure cascade

The deadlock propagates through at least 25 devices:

- **ADSP** (`ACPI\QCOM0C1B`) and **CDSP** (`ACPI\QCOM0CB0`) — `CM_PROB_FAILED_ADD`
- **QCPEP thermal/policy cluster** — 17 devices, `STATUS_NO_SUCH_DEVICE`
- **Bluetooth radio** — transport OK; radio not enumerated
- **Audio** — fully blocked by ADSP failure
- **Adreno GPU** (`ACPI\VEN_QCOM&DEV_0D17`) — failing
- **Battery reporting** — blocked

> **Scope note.** Several additional devices (ADC `QCOM0C11`, UART `QCOM0C16`,
> Human Presence Sensor `QCOM06D9`, EVA `QCOM0CF1`, ISP Camera `QCOM0C32`, HID
> Button `ACPI0011`) are listed in `docs/Driver_Reference_Map.md` as still failing.
> These are **not yet proven to be downstream** of the QCSP/SPSS deadlock. They may
> have independent causes. Which of them resolve when the deadlock is broken cannot
> be determined until the deadlock is actually broken.

---

## 6. Evidence Matrix

| Claim | Evidence type | Evidence | Strength |
|---|---|---|---|
| QCSP `_DEP` includes `\_SB.SPSS` | Direct | DSDT disassembly (`iasl -d`) shows `_DEP` package contains `\_SB.GLNK`, `\_SB.SOCP`, `\_SB.SPSS` | **Direct** |
| QCSP absent from PnP | Direct | `Get-PnpDevice` returns no `QCOM0C87` entry; Device Manager shows no such device; Kernel-PnP log (732 events) has zero entries for `ACPI\QCOM0C87`; `setupapi.dev.log` has no hardware-initiated install entry for it; `HKLM\...\Enum\ACPI` has no `QCOM0C87` subkey | **Direct** |
| SPSS fails to start | Direct | SPSS reports `CM_PROB_FAILED_ADD` with `STATUS_OBJECT_NAME_NOT_FOUND`; confirmed reproducible across sessions | **Direct** |
| SPSS start is being held pending at the kernel level | Direct (in-memory) | Live kernel debugger (`kdARM64.exe -kl`): `!devobj` on the SPSS device object shows `ExtensionFlags = DOE_START_PENDING` — the literal, live kernel flag meaning "this device's start IRP is being withheld" (Session 51, 2026-06-08) | **Direct** |
| Windows dependency database records QCSP as SPSS's dependent | Direct | `DEVPKEY_Device_DependencyDependents` on `ACPI\QCOM0C8D` = `\_SB.QCSP` (ACPI namespace path format, used for devices that were never presented to PnP, as distinct from the PnP instance-ID format used for devices that were presented but failed). GLNK (running, OK) lists 9 dependents as PnP instance IDs including SPSS itself — SPSS *was* presented to PnP and is in GLNK's list. QCSP is not in GLNK's list. Only SPSS (failed) retains `\_SB.QCSP` as an ACPI path. (Session 49–50) | **Direct** |
| PIL TZ interface is inactive | Direct | PIL TZ `Linked` value blank or absent at `HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}\#`; reproducible across all sessions | **Direct** |
| ACPI `_DEP` informs device start ordering | Established fact | ACPI specification: `_DEP` lists objects that must be functional before the declaring device is presented to OSPM | **Established** |
| Windows withholds QCSP **because** `\_SB.SPSS` is unresolved | Strongly indicated | All directly-observed states are consistent: SPSS failed; Windows dependency database records QCSP as SPSS's dependent using the ACPI-path format (never-presented); QCSP absent from all PnP logs; WPR boot trace confirmed the ACPI/PnP `_DEP`-gate decision is not emitted as ETW events — the gate mechanism is not observable through any tested provider | **Strongly indicated — ACPI `_DEP` gate itself not directly captured** |
| `qcsubsys.sys` fails because PIL TZ is absent | Inferred | `STATUS_OBJECT_NAME_NOT_FOUND` correlates with blank PIL TZ `Linked`; the more specific NTSTATUS `STATUS_OBJECT_PATH_COMPONENT_NOT_A_DIRECTORY` (from `!error 0xC000003B` in Session 51) suggests an Object Manager path traversal failure during init | **Inferred — not traced via symbols or disassembly** |
| Raw AML byte patch after boot is insufficient to break the deadlock | Direct test | DSDT pool copy located at physical `0xD4781018`, bytes confirmed, write succeeded, checksum fixed; `pnputil /scan-devices` rescan: all three oracles unchanged. `acpi.sys` builds the ACPI namespace once at boot from raw AML and evaluates `_DEP` from the cached parsed object thereafter (Session 52, 2026-06-09) | **Direct** |
| Patching `_DEP[2]` SPSS→GLNK at firmware time would break the deadlock | Unconfirmed | Follows from the model; the UEFI-time fix (D8b: MAP unprotect + patch before `ExitBootServices`) has not yet been tested with the correct MAP GUID | **Untested** |
| Secondary device failures are downstream of the deadlock | Plausible / unproven | Device failures align with Qualcomm subsystem cascade; not individually verified | **Unproven — must be retested after deadlock is broken** |
| Factory image would avoid the deadlock | Hypothesis | Device worked at unboxing; factory image may include different ACPI state or provisioning | **Untested — no factory image was compared** |

---

## 7. Failed Remediation Attempts

### 7.1 Standard ACPI override paths

All four standard mechanisms are dead on Windows ARM64 / Insyde H2O V1.09:

| Attempt | Approach | Result | Reason |
|---|---|---|---|
| 1 | `HKLM\...\acpitables` + `ACPIOVERRIDETEST` BCD | Dead | x86/BIOS-only; ARM64 `winload.efi` has no code path that reads this key |
| 2 | SSDT files in ESP (`S:\EFI\ACPI\`, etc.) | Dead | Insyde firmware on this board does not load ESP SSDTs |
| 3 | Binary-patched DSDT via `acpitables` | Dead | Same ARM64 limitation as Attempt 1 |
| 4 | GRUB2 `acpi` module + chainloader | Dead | GRUB modifies XSDT in RAM but does not update the EFI ConfigurationTable RSDP pointer; `winload.efi` follows the original RSDP |

The architectural reason for failures 1–3: ARM64 `winload.efi` reads ACPI tables
exclusively from the EFI System Table's `ConfigurationTable` array. The `acpitables`
registry key and `ACPIOVERRIDETEST` BCD flag exist only in x86/x64 `winload`. For
failure 4: GRUB's `acpi` module predates the ARM64 EFI boot path and does not update
the pointer `winload.efi` actually follows.

### 7.2 Custom UEFI application — 15 sub-attempts (5a–5o)

After the four standard paths failed, a custom PE32+ AARCH64 EFI application
(`AcpiInject.efi`) was built and iterated through 15 sub-attempts. Summary:

| Attempt | Approach | Result |
|---|---|---|
| 5a–5c | GRUB chainloader → `AcpiInject.efi`; fixed PE headers | Load-time rejections (Shim, ARM64 permission fault, bad PE headers) |
| 5d–5g | Working binary; file logging | Firmware blocks all SFS file I/O from UEFI app context |
| 5h | NVRAM variable logging | Firmware blocks `SetVariable`/`GetVariable` for all variables (error 1314); also revealed wrong ACPI GUID in 5a–5g |
| 5i–5j | Direct XSDT modification; write `RSDP->XsdtAddress` | RSDP is in firmware read-only memory; write silently dropped |
| 5k | DSDT in-place `_DEP` byte patch | DSDT pages also read-only; write silently dropped |
| 5l–5m | `EFI_MEMORY_ATTRIBUTE_PROTOCOL` unprotect + patch | **INVALID — wrong GUID** (`{6A7A5CFF...}` = `EFI_COMPONENT_NAME2_PROTOCOL`, not MAP). MAP was never invoked. Retest pending (D8b). |
| 5n–5o | `BootServices->InstallConfigurationTable()` with replacement RSDP/XSDT/SSDT chain | Call may succeed but Windows does not parse the replacement chain; only firmware's own `Compal` SSDT visible after boot |

Full detail in [`docs/EFI_Injection_Tracking.md`](docs/EFI_Injection_Tracking.md).

**Central finding from §7.2:** The RSDP, XSDT, FADT, and DSDT on this Insyde H2O
V1.09 platform all reside in firmware-managed read-only EFI memory pages. Writes do
not raise an ARM64 permission fault — they are silently dropped. Additionally, all
diagnostic channels an EFI application might use (file I/O, NVRAM variables) are
blocked by the firmware. Even the firmware's own `InstallConfigurationTable()` service
does not result in Windows parsing a replacement ACPI chain.

### 7.3 Post-boot kernel DSDT patch (Session 52)

The Windows-visible DSDT pool copy was located at physical address `0xD4781018`.
The bytes `53 50 53 53` ("SPSS") at offset `0x36C69` were confirmed. A physical-memory
write succeeded: the bytes changed to `47 4C 4E 4B` ("GLNK") and the DSDT checksum
was corrected. A `pnputil /scan-devices` rescan was performed.

**Result:** All three oracles (QCSP absent, SPSS failing, PIL TZ not linked) were
unchanged. `acpi.sys` builds the ACPI namespace from raw AML once at boot and
evaluates `_DEP` from the cached parsed namespace object. It does not re-parse AML
on a device rescan. Patching the raw bytes after boot has no effect on device
enumeration.

**Conclusion:** Any DSDT patch must occur before `acpi.sys` reads the AML at boot.
Post-boot raw AML patching is not sufficient.

---

## 8. Pending Retests: D8a and D8b

Two UEFI injection approaches were invalidated by a wrong-GUID bug in the earlier
builds and have not yet been retested with the correct GUIDs. These are the last
remaining in-band software paths.

### 8.1 D8a — `EFI_ACPI_TABLE_PROTOCOL` retest

**Status: PENDING**

The earlier builds (5a–5g) used GUID `{8D59D32B-C655-4AE9-9B15-F25904992A43}`
(`EFI_ABSOLUTE_POINTER_PROTOCOL`) instead of the correct ACPI table protocol GUID.
The correct GUID is:

```
EFI_ACPI_TABLE_PROTOCOL
{FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}
```

A clean retest (`AcpiInject_D8a.efi`) must:
- Call `BootServices->LocateProtocol()` with the correct GUID
- Log the exact EFI status returned (`EFI_SUCCESS`, `EFI_NOT_FOUND`, `EFI_ACCESS_DENIED`, or other)
- On `EFI_SUCCESS`: call `InstallAcpiTable()` with an 80-byte canary SSDT (`_HID = "QCOM1234"`)
- After boot: check `HKLM\HARDWARE\ACPI\SSDT` and `Get-PnpDevice` for `ACPI\QCOM1234`

**Expected outcomes and what they mean:**
- `EFI_NOT_FOUND` + no canary: protocol is absent on this firmware
- `EFI_ACCESS_DENIED` or `EFI_INVALID_PARAMETER`: protocol present but rejects the call
- `EFI_SUCCESS` + canary in SSDT: injection is possible via this protocol

Until D8a is run with the correct GUID and a working diagnostic channel, the
availability of `EFI_ACPI_TABLE_PROTOCOL` on this firmware is **unknown**.

### 8.2 D8b — `EFI_MEMORY_ATTRIBUTE_PROTOCOL` retest

**Status: PENDING**

Attempts 5l and 5m used GUID `{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}`
(`EFI_COMPONENT_NAME2_PROTOCOL`) — not MAP. The correct GUID is:

```
EFI_MEMORY_ATTRIBUTE_PROTOCOL
{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}
```

(Verified against EDK2 master `MdePkg/Include/Protocol/MemoryAttribute.h`.)

A clean retest (`AcpiInject_D8b.efi`) must:
- Call `BootServices->LocateProtocol()` with the correct MAP GUID
- Log the EFI status
- On `EFI_SUCCESS`: call `ClearMemoryAttributes()` on the DSDT page to clear `EFI_MEMORY_RO`
- Perform a canary write to `DSDT[0x20..0x23]` (CreatorRevision)
- After boot: check `HKLM\HARDWARE\ACPI\DSDT\...\00000000` at offset `0x20` for the canary bytes

The GUID correction has been applied to `efi-injection/build_efi.py` as of
2026-06-09.

**If D8b succeeds** (MAP present, write-protection cleared, canary bytes survive boot),
the actual `_DEP` patch (SPSS→GLNK at offset `0x36C69`) can be applied and tested.

---

## 9. Kernel and ETW Diagnostic Findings

These findings document what the diagnostic work established and — importantly —
where it hit confirmed limits.

### 9.1 Kernel-PnP static log (Session 49)

The `Microsoft-Windows-Kernel-PnP/Configuration` event log (732 events, all boots)
and `setupapi.dev.log` were searched for `QCOM0C87`, `QCOM0C8D`, `_DEP`, and
dependency keywords. Key results:

- SPSS (`ACPI\QCOM0C8D`): Event 411 present — "had a problem starting", Problem
  `0x1F` / `0xC000003B`
- QCSP (`ACPI\QCOM0C87`): **zero events** in Kernel-PnP log; zero hardware-initiated
  entries in setupapi — confirmed never presented to the PnP manager
- `DEVPKEY_Device_DependencyDependents` on SPSS records `\_SB.QCSP` in ACPI namespace
  path format (used for devices that were evaluated for `_DEP` but never presented),
  as distinct from GLNK's dependent list which uses PnP instance IDs

### 9.2 WPR boot trace — confirmed limitation (Session 50)

A custom WPR boot-trace profile was armed with five providers:
`Microsoft-Windows-Kernel-Acpi`, `ACPI Driver Trace Provider`,
`Microsoft-Windows-Kernel-PnP`, `Microsoft-Windows-Kernel-Boot`, and
`Microsoft-Windows-DriverFrameworks-UserMode`. Full reboot captured with
`wpr -stopboot`.

**Result:** The four ACPI/PnP/Boot providers logged **zero events of any kind**.
The fifth provider (`DriverFrameworks-UserMode`) did produce real events for two
unrelated UMDF devices, confirming the profile was honored — the silence from the
other four is a genuine negative, not a misconfiguration. The `acpi.sys` `_DEP`-gate
decision fires too early and/or is not instrumented by any provider available in a
standard WPR boot-trace profile on this system/build.

**Interpretation:** The ETW path cannot promote the root-cause model from "strongly
indicated" to "proven." This is a confirmed limitation, not a missing step.

### 9.3 Live kernel debugger inspection (Session 51)

With `bcdedit /debug on` and `kdARM64.exe -kl`, the SPSS device object was located
and inspected:

- `!devobj` showed `ExtensionFlags = DOE_START_PENDING` — the literal live kernel flag
  meaning "this device's start IRP is being withheld." This is a first-hand, in-memory
  observation of the state the root-cause model predicts.
- `!devstack` showed the SPSS PDO is owned solely by `\Driver\ACPI` with no FDO —
  confirming `qcsubsys.sys` never attached.
- `!error 0xC000003B` decoded SPSS's Problem Status to
  `STATUS_OBJECT_PATH_COMPONENT_NOT_A_DIRECTORY` — a more specific NTSTATUS than the
  generic `CM_PROB_FAILED_ADD` label suggests; indicates an Object Manager path
  traversal failure during init.

A targeted string search for `QCOM0C87`/`QCSP`/`\_SB.QCSP` over a pre-targeted 2 MB
window returned a clean negative. Wider range searches (32 MB, 2 GB) hung
indefinitely — confirming a tooling limit, mirroring the Session 50 ETW conclusion.

---

## 10. Limitations

1. **Only one hardware unit tested.** All observations are from a single Acer
   A14-11M (NX.JP3ED.002, firmware V1.09). Behavior may differ across BIOS
   versions, regional SKUs, or related Snapdragon X 8380 boards.

2. **No factory image comparison performed.** Whether a working A14-11M uses the
   same DSDT (firmware bug confirmed) or avoids the deadlock through provisioning
   or load order (software-side cause) is unknown. This is the highest-value
   remaining validation path.

3. **The exact Windows ACPI `_DEP` gate decision has not been directly observed.**
   ETW/WPR boot tracing confirmed the relevant providers emit zero events on this
   system. The `acpi.sys` gate mechanism is not externally observable through
   standard instrumentation. The root-cause model is strongly indicated by correlated
   direct evidence but is not vendor-grade proven.

4. **`EFI_ACPI_TABLE_PROTOCOL` availability is unknown.** The only test using this
   protocol (5h) had the correct GUID but no working diagnostic channel to confirm
   the returned EFI status. D8a will resolve this.

5. **`EFI_MEMORY_ATTRIBUTE_PROTOCOL` was never actually invoked.** Attempts 5l and
   5m used the wrong GUID. D8b will resolve this.

6. **Secondary device failures not individually verified.** Several failing devices
   may have causes independent of the QCSP/SPSS deadlock. This cannot be determined
   until the deadlock is broken and a baseline diff is taken.

7. **Driver internals not confirmed.** That `qcsubsys.sys` fails specifically because
   it opens the PIL TZ interface is inferred from the NTSTATUS correlation, not from
   private symbols or a debugger trace of the driver.

8. **Firmware behavior may vary.** The specific read-only ACPI memory behavior,
   blocked variable services, and blocked SFS I/O are observed on Insyde H2O V1.09
   for NX.JP3ED.002. Other Insyde builds or other firmware vendors may behave
   differently.

---

## 11. Remediation Paths

### 11.1 Firmware fix (preferred)

A BIOS update for NX.JP3ED.002 that removes `\_SB.SPSS` from QCSP's `_DEP`, or that
changes device initialization order so QCSP initializes before SPSS requires PIL TZ.
This is the preferred permanent fix and requires no further software work if Acer
ships it. V1.09 is the latest available as of May 2026.

Verification after a new BIOS: `ACPI\QCOM0C87` appears in PnP and PIL TZ `Linked`
reads `1`.

### 11.2 Factory image recovery

The Acer-supplied recovery media may restore the original OEM state in which the
device worked. This is a plausible workaround but is **not a firmware fix** — the
underlying DSDT `_DEP` issue, if it exists in the shipping firmware, would persist
and recur on any clean reinstall. A factory-image comparison (see Limitation 2) is
required to establish whether this is true.

### 11.3 Driver-only partial recovery

Safe single-INF installation (§3–§4) restores roughly 60% of the Qualcomm platform
stack. This is the currently confirmed best achievable state without breaking the
deadlock.

### 11.4 UEFI injection — pending D8a and D8b

Two correct-GUID retests remain. If either succeeds:
- D8a success: `EFI_ACPI_TABLE_PROTOCOL->InstallAcpiTable()` with the 80-byte stub
  SSDT (`efi-injection/ssdt_qcsp.aml`) can inject the fix with no firmware patch needed
- D8b success: MAP unprotect + DSDT byte patch at `0x36C69` (SPSS→GLNK) before
  `ExitBootServices` would fix the DSDT at firmware load time

### 11.5 Offline BIOS ROM modification

Patch the DSDT `_DEP` at offset `0x36C69` inside the firmware image using UEFITool
or Insyde tooling, then reflash. Risk: **high** — a failed reflash can brick the
device. Requires a verified full firmware backup and an external recovery path.

### 11.6 OS-side workarounds (untried; complex)

Candidate approaches: ACPI filter driver publishing PIL TZ before `qcsubsys.sys`
requests it; phantom `QCOM0C87` devnode via `IoReportDetectedDevice`; boot-start
staging of `qcsp.sys`. All require kernel driver signing or WHQL approval, which is
non-trivial with HVCI ON, and have not been attempted.

---

## 12. Vendor Engagement

A detailed technical writeup of the DSDT `_DEP` chain, the PIL TZ inactive state,
the absence of `ACPI\QCOM0C87` from PnP, and the `CM_PROB_FAILED_ADD` failures on
ADSP, CDSP, and SPSS was submitted to Acer support. The writeup identified the
failure as a firmware-level ACPI dependency-ordering issue and requested either a
BIOS update removing SPSS from QCSP's `_DEP`, or guidance on obtaining the
OEM-provisioned driver state present at unboxing.

After approximately seven days, Acer support replied with four lines: try Windows
Update, and if that does not work, purchase physical recovery media. The reply
showed no engagement with the technical content of the submitted writeup and no
escalation to a firmware or BIOS team. The verbatim reply (original Danish, signed
"Max"):

> Prøv i første omgang at opdatere drivere direkte fra Microsoft: [link]
> Hvis det ikke løser problemet kan du bestille usb recovery på denne side: [link]

Neither step addresses the documented bug. Windows Update does not ship Insyde
firmware updates for this SKU and does not modify firmware ACPI tables. The failure
profile persists across all Windows Update cycles on this device. The recovery media
option requires the customer to pay and wait for physical media to be delivered —
to restore a working state on a warranty-active, defect-free device where the failure
was caused by following standard manufacturer and Microsoft reinstall procedures, not
by any hardware fault.

The response was received on 22 May 2026. As of 8 June 2026 — more than two weeks
later — there has been no further communication: no follow-up, no escalation, no
acknowledgment of the technical content.

The author remains willing to share the full failure chain with anyone at Acer or
Qualcomm able to act on it.

---

## 13. Conclusion

After a clean Windows 11 ARM64 reinstall on the Acer A14-11M (NX.JP3ED.002), a
circular ACPI `_DEP` dependency in the Insyde H2O V1.09 firmware prevents the QCSP
device (`ACPI\QCOM0C87`) from ever being presented to the Windows PnP manager. This
causes SPSS to fail, which cascades into ADSP, CDSP, the QCPEP thermal cluster,
Adreno GPU, audio, and Bluetooth radio.

The evidence for this model is strong: the `_DEP` relationship is directly read from
the DSDT; QCSP is confirmed absent from all PnP logs; SPSS is confirmed failing with
`DOE_START_PENDING` visible in live kernel memory; the Windows dependency database
records `\_SB.QCSP` as SPSS's dependent in the ACPI namespace path format used only
for never-presented devices. The one link not directly traced — that `acpi.sys`
withholds QCSP *specifically* because `\_SB.SPSS` is unresolved — is strongly
indicated but remains inferred, after ETW boot tracing confirmed the relevant
providers emit zero events on this system.

Safe single-INF driver installation restores 60% of the platform stack and is
documented as a reproducible recipe. All tested in-band ACPI table modification
paths from a UEFI boot application have failed on this firmware, primarily because
the ACPI memory pages are firmware-managed read-only. Two corrected protocol retests
(D8a, D8b) remain to close the last in-band software options. A firmware update from
Acer remains the preferred fix.

---

## Appendix A — Repository layout

```
README.md                       Landing page and current status
paper.md                        This document — the research paper
reproduce.md                    Minimum reproducible test case
vendor_summary.md               One-page vendor escalation summary

docs/
  FINDINGS.md                   Earlier synthesised findings (full detail)
  SESSION_LOG.md                Chronological lab notebook (54+ sessions)
  ATTEMPTS.md                   Concise attempt table
  EFI_Injection_Tracking.md     Full UEFI injection sub-attempt log (5a–5o)
  AcpiInject_Findings.md        PE binary analysis; identified the wrong-GUID bug
  Driver_Reference_Map.md       Hardware ID to INF mapping table
  INDEX.md                      Navigation map, glossary, attempt index

efi-injection/
  build_efi.py                  Python builder for AcpiInject.efi
  ssdt_qcsp.asl                 SSDT ASL source (human-readable)
  ssdt_qcsp.aml                 Compiled 80-byte stub SSDT
  ssdt_test.asl                 Canary SSDT (QCOM1234) for injection verification

baselines/                      Milestone PnP device CSV snapshots
```

## Appendix B — Key identifiers and GUIDs

| Identifier | Value |
|---|---|
| QCSP hardware ID | `ACPI\QCOM0C87` |
| SPSS hardware ID | `ACPI\QCOM0C8D` |
| PIL TZ device interface GUID | `{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}` |
| DSDT registry path | `HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000` |
| DSDT `_DEP[2]` patch offset | `0x36C69` |
| `_DEP[2]` original bytes | `53 50 53 53` ("SPSS") |
| `_DEP[2]` target bytes | `47 4C 4E 4B` ("GLNK") |
| `EFI_ACPI_TABLE_PROTOCOL` GUID | `{FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}` |
| `EFI_MEMORY_ATTRIBUTE_PROTOCOL` GUID | `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}` |
| ACPI 2.0 ConfigurationTable GUID | `{8868E871-E4F1-11D3-BC22-0080C73C8881}` |
| `qcsp.sys` INF (Acer OEM) | `oem102.inf` (v1.0.4196.6900) |
| `qcsp.sys` INF (WOA-Project) | `oem103.inf` (v1.0.4478.2200) |

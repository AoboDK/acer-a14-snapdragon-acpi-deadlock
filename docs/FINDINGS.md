# Acer A14-11M — Qualcomm Driver Recovery on Windows 11 ARM64

> **Superseded for new readers.** The clean research paper is now [`../paper.md`](../paper.md).
> This document is retained because it is cross-referenced throughout `INDEX.md`,
> `SESSION_LOG.md`, `ATTEMPTS.md`, and the session handoff notes. All internal links
> remain valid. New readers should start with `paper.md`.

> For the chronological lab notebook, see [`SESSION_LOG.md`](SESSION_LOG.md).
> For the navigation map, see [`INDEX.md`](INDEX.md). For the concise attempt summary,
> see [`ATTEMPTS.md`](ATTEMPTS.md).

---

## §1 Abstract

This paper documents an investigation into Qualcomm platform driver recovery on an
Acer A14-11M (product code NX.JP3ED.002) laptop equipped with a Qualcomm Snapdragon
X 8380 SoC (SUBSYS_CRD08380), running Windows 11 ARM64 26H1 (Build 26200) on Insyde
H2O firmware version V1.09.

After a clean Windows 11 ARM64 installation on this SKU, approximately 40 Qualcomm
platform devices fail to start. The affected devices include the ADSP, CDSP, and SPSS
subsystems (problem code `CM_PROB_FAILED_ADD`), a cluster of 17 QCPEP thermal and
policy devices (`STATUS_NO_SUCH_DEVICE`), and the Adreno GPU. Audio, Bluetooth, and
battery reporting are blocked as downstream consequences. The QCSP device
(`ACPI\QCOM0C87`) is absent from the Windows PnP tree entirely.

The root cause is **strongly indicated** to be a circular dependency deadlock encoded
in the system DSDT. The QCSP device (`_HID = "QCOM0C87"`) carries an `_DEP` reference
to `\_SB.SPSS`. SPSS (`ACPI\QCOM0C8D`) cannot complete `AddDevice` because the PIL TZ
interface (`{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`) is not active. That interface is
activated by `qcsp.sys` — the driver for QCSP — but `qcsp.sys` never loads because QCSP
appears to be held back by Windows ACPI's unsatisfied-`_DEP` gate. The deadlock is
self-referential and cannot be broken by driver installation alone.

This model is built from directly-observed device and registry state plus the DSDT
contents; the one link not directly traced is that Windows withholds `QCOM0C87`
*specifically* because `\_SB.SPSS` is unresolved (inferred, not captured via
ETW/WinDbg). The proof status of each element, and the validation steps that would
confirm it, are stated in [§6](#limitations-and-proof-status) and [§11](#11--open-questions-untried-and-unproven-paths).
It should be read as a strongly-supported hypothesis, not a vendor-grade proven fault.

Four standard ACPI override mechanisms were tested and failed: the
`HKLM\SYSTEM\CurrentControlSet\Control\acpitables` registry override with the
`ACPIOVERRIDETEST` BCD flag (x86/BIOS-only; ignored on ARM64), SSDT files placed in
ESP paths (Insyde firmware on this board does not load them), a binary-patched DSDT
loaded via the same `acpitables` mechanism (same ARM64 limitation), and the GRUB2
`acpi` module with chainloader (modifies XSDT in RAM but does not update the EFI
ConfigurationTable RSDP pointer; Windows ARM64 ignores it). Fifteen sub-attempts of a
custom PE32+ AARCH64 EFI injection application (`AcpiInject.efi`) were then
exhausted, revealing that the RSDP, XSDT, FADT, and DSDT on this Insyde H2O V1.09
platform all reside in firmware-managed read-only memory pages that cannot be modified
by a UEFI application, and that even the firmware's own
`BootServices->InstallConfigurationTable()` service does not cause Windows to parse a
replacement ACPI chain.

What is exhausted is specifically **in-band ACPI table injection from a UEFI boot
application** — not every conceivable avenue. The two firmware *fix* routes are out of
band (a future Acer BIOS update for NX.JP3ED.002 that removes SPSS from QCSP's `_DEP`,
or offline BIOS ROM modification). Beyond them, a set of **untried** paths — both
*validation* paths that would prove or refute the root cause (a factory-image
comparison, an ETW/WinDbg `_DEP`-gate trace, a cross-device DSDT comparison, a
live-kernel DSDT patch) and *candidate fixes* outside the UEFI-injection path (rEFInd,
the UEFI Shell, an alternate ACPI protocol GUID, OS-side kernel circumvention) — are
catalogued honestly in §11; none have been attempted and none are claimed to work. Acer
support offered Windows Update and the purchase of physical recovery media; neither
addresses the firmware-level DSDT defect. The case remains open as of June 2026, with no
Acer follow-up since the single 22 May 2026 reply.

---

## §2 Hardware and system under test

| Field | Value |
|---|---|
| Model | Acer Swift 14 AI (A14-11M), product code NX.JP3ED.002 |
| SoC | Qualcomm Snapdragon X 8380 (SUBSYS_CRD08380) |
| OS | Windows 11 ARM64 26H1, Build 26200 |
| UEFI firmware | Insyde H2O (QCOMM_/SDM8380_/rev3), V1.09 |
| UEFI version status | V1.09 is the latest available for this SKU as of May 2026 |
| Secure Boot | OFF (disabled for testing; factory default is ON) |
| HVCI (Memory Integrity) | ON |

> **Key memory-map fact:** The RSDP, XSDT, FADT, and DSDT on this platform all
> reside in firmware-managed EFI memory pages. Writes to those pages from a UEFI
> application are silently dropped — no ARM64 permission fault is raised. This is
> the central constraint that blocks all software-only ACPI table modification
> approaches. See [§9 Finding 5](#9-finding-5--firmware-managed-read-only-acpi-memory)
> and [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md) for the full evidence.

---

## §3 Problem statement

### How the device reached this state

The recovery effort documented in this paper began with a routine attempt to
refresh the operating system. The factory Windows install was wiped using the
built-in **Settings → System → Recovery → Reset this PC** function. After the
reset completed and the machine attempted to restart, it failed to boot: it hung
in a loop at the Acer boot logo and never reached Windows. At that point the
device was unbootable by its own built-in recovery path.

With the in-box reset having left the machine unbootable, the only remaining
route back to a working OS was a clean reinstall from external media. A fresh
Windows 11 ARM64 image was downloaded directly from Microsoft and written to a
USB drive (see *Install procedure* below). Every observation in this paper was
made under this clean USB reinstall — not under the original factory image.

This origin matters to the findings. The defect documented here is not an
artifact of an exotic or unsupported installation method: the user reached for
the manufacturer- and Microsoft-sanctioned recovery paths first — the built-in
Windows "Reset this PC", then an official Microsoft Windows 11 ARM64 ISO — and
the platform-driver deadlock in §6 is what remained after both.

### Install procedure

The investigation was conducted on a Windows 11 ARM64 26H1 install performed
directly on the A14 using the FAT32-USB + split-WIM method documented by t0ma5 in
[caccialdo's gist](https://gist.github.com/caccialdo/3b0d0113489ecee456d94c1e9462d755).
The procedure splits `install.wim` into `.swm` parts using `Dism /Split-Image` to
work around FAT32's 4 GB file size limit, copies the resulting parts onto a
FAT32-formatted USB drive, and boots the installer from a USB-C port. USB-A ports
produce a "missing drivers" error on this device and cannot complete the installation.

> **Footnote:** An earlier one-off test used offline DISM apply from another PC; the
> resulting driver state was the same. That test does not reflect the install state
> under which the investigation was conducted.

### Failure profile after install

After install, a `Get-PnpDevice` query returns approximately 40 non-OK devices. The
principal failures are:

- **ADSP** (`ACPI\QCOM0C1B`): `CM_PROB_FAILED_ADD` (problem code 31)
- **CDSP** (`ACPI\QCOM0CB0`): `CM_PROB_FAILED_ADD`
- **SPSS** (`ACPI\QCOM0C8D`): `CM_PROB_FAILED_ADD`
- **QCPEP thermal/policy cluster** (17 devices): `STATUS_NO_SUCH_DEVICE`
- **Adreno GPU**: failing
- **Bluetooth radio**: unenumerated (transport layer present, radio device absent)
- **Audio**: blocked by ADSP failure
- **Battery reporting**: blocked

The PIL TZ device interface (`{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`) is registered
in the Windows device class registry at
`HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`
but the `Linked` value under the `#` subkey is blank rather than `1`. The QCSP
device (`ACPI\QCOM0C87`) does not appear in the PnP device tree at all.

### The Setup_Driver.cmd BSOD trap

Acer's bundled `Setup_Driver.cmd` from the 0.7700.1 driver package performs a bulk
recursive install of every driver in the package in a single pass using
`pnputil /subdirs /install`. On a system already in the broken post-install state,
running this script triggers a **"SOC critical device removed" BSOD** mid-install.
Recovery requires a restore point or full re-image. This script must not be used on
any system in this state. The safe alternative is documented in [§4 Methodology](#4-methodology).
Full session context is in [`SESSION_LOG.md`](SESSION_LOG.md).

### Exit criteria for "fixed"

The investigation is complete when all of the following conditions hold simultaneously:

1. `Linked=1` at `HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}\#`
2. `ACPI\QCOM0C87` appears in the PnP device tree
3. SPSS (`ACPI\QCOM0C8D`) no longer reports `CM_PROB_FAILED_ADD`
4. ADSP and CDSP start successfully
5. Audio, Bluetooth, and Adreno GPU are restorable to working state

---

## §4 Methodology

The investigation followed a consistent discipline across all 48 sessions. This
section documents that discipline as a reproducible recipe.

### Safe single-INF install rule

All driver installations use only:

```powershell
pnputil /add-driver "C:\path\to\driver.inf" /install
```

The `/subdirs` flag and any bulk or recursive install command are prohibited on this
system in its current state. One INF at a time, with a deliberate reboot between
high-risk drivers.

### Stage-only-first for high-risk platform drivers

The following drivers are installed in stage-only mode first (`/add-driver` without
`/install`), followed by a reboot, followed by a baseline CSV export and diff, before
any decision to proceed:

- `qcpep` (thermal/policy engine)
- `qcpil` (PIL loader)
- `qcsmmu` (IOMMU/SMMU)
- `qcsubsys` (subsystem manager)
- `qcscm` (secure channel manager)

These drivers are classified high-risk because a version mismatch or load failure
can produce the "SOC critical device removed" BSOD. Stage-only first allows
verification that the INF matches the hardware ID before the driver becomes active.

### Restore point before medium-risk and high-risk phases

A Windows System Restore point is created before any session that installs or
modifies platform drivers rated medium-risk or high-risk. This makes the 3×
power-interrupt BSOD recovery path viable without relying solely on a disk image.

### Baseline CSV diffing as the primary feedback loop

Before and after each driver phase, a baseline CSV is exported to the `baselines\`
subfolder using the following exact command:

```powershell
Get-PnpDevice |
    Where-Object { $_.Status -ne "OK" } |
    Where-Object { $_.InstanceId -notlike "SWD\MSRRAS*" } |
    Select-Object Class, FriendlyName, Status, Problem, InstanceId |
    Export-Csv -Path "$env:USERPROFILE\Desktop\A14\baselines\A14_Baseline_$(Get-Date -Format yyyyMMdd_HHmmss).csv" -NoTypeInformation
```

The CSV pair (before and after) is the primary signal for whether a driver phase made
progress, regressed, or had no effect. Device Manager is used as a secondary
confirmation tool.

### The PIL TZ `Linked=1` oracle

The single most important signal in the investigation is the `Linked` value under
the PIL TZ device interface registry key:

```
HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}\#
```

`Linked=1` means `qcsp.sys` has loaded and activated the PIL TZ interface — the
deadlock is broken. `Linked` absent or blank means the deadlock persists. This is the
definitive go/no-go signal for any injection attempt or driver phase.

To check from PowerShell:

```powershell
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
$base = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid"
Get-ChildItem $base -Recurse | Get-ItemProperty | Select-Object PSPath, Linked
```

### The DSDT byte oracle

The live DSDT as Windows sees it is readable from the registry at:

```
HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000
```

Reading bytes `[0x36C69..0x36C6C]` from this value reveals whether any injection
attempt has patched the QCSP `_DEP[2]` target:

- `53 50 53 53` ("SPSS") — DSDT is in the original broken state
- `47 4C 4E 4B` ("GLNK") — DSDT has been successfully patched

This four-byte oracle provides an unambiguous signal independent of PnP or service
state. The same registry read of the live DSDT is used as a canary in Attempt 5m
(§8): a known pattern written to a benign DSDT field (the CreatorRevision at
`DSDT[0x20..0x23]`) after a `EFI_MEMORY_ATTRIBUTE_PROTOCOL` unprotect attempt
either appears in the registry after boot (the write landed) or does not (the
write was silently dropped), without requiring a visible behavior change.

### BSOD recovery procedure

If a driver installation produces a "SOC critical device removed" or other critical
BSOD:

1. Allow the system to attempt restart. If it loops at the boot logo, interrupt power
   three times in sequence during the Acer splash screen phase.
2. Windows Recovery Environment launches automatically after three interrupted boots.
3. Navigate to: Troubleshoot → Advanced options → System Restore.
4. Select the restore point created before the failing driver phase.
5. Allow the restore to complete and reboot normally.

Full phase-by-phase session history, including exact commands and outcomes, is in
[`SESSION_LOG.md`](SESSION_LOG.md). The four milestone baseline CSVs are in
`baselines/`.

---

## §5 — Finding 1: Safe driver recovery — what works, and where it stops

### Summary

A partial recovery of the Qualcomm platform stack is achievable on the Acer A14-11M
after a clean Windows 11 ARM64 reinstall, using a disciplined single-INF installation
approach. Approximately 60% of the platform stack can be restored to a working state.
The remaining 40% is blocked by a firmware-level circular dependency that cannot be
resolved by driver installation alone. The boundary between these two zones is precise
and reproducible.

### What is restored

The following components reach a working or running state after safe single-INF installs:

| Component | Status after recovery |
|---|---|
| WiFi | Working |
| Display | Working |
| Keyboard, Trackpad | Working |
| USB, Card Reader | Working |
| Camera | Working |
| NPU | Working |
| PMIC Apps (`qcpmicapps`) | Running |
| PMIC GLink (`qcpmicglink`) | Running |
| TFTP (`qcTFTP`) | Running |
| SCM (`qcscm`) | Running |
| GLINK (`qcGLINK`) | Running |
| IPC Router (`qcIPCR`) | Running |
| IPCC (`qcIPCC`) | Running |
| Syscache (`qcsyscache`) | Running |
| SMMU (`qcsmmu`) | Running |
| PIL — `qcPILC` | Running |
| PIL Filter — `qcPILFC` | Running |
| `qcsubsys` service | Running |

### The safe install pattern

Every driver must be installed using the single-INF invocation:

```powershell
pnputil /add-driver "C:\path\to\driver.inf" /install
```

The `/subdirs` flag must never be used. Running Acer's bundled `Setup_Driver.cmd`
from the 0.7700.1 package is explicitly unsafe: it bulk-installs all INFs in one
pass and caused a "SOC critical device removed" BSOD on an already-partial install,
requiring a full restore-point rollback to recover. The same BSOD risk applies to any
other batch or recursive install command.

For high-risk platform drivers — `qcpep`, `qcpil`, `qcsmmu`, `qcsubsys`, `qcscm` —
the recommended sequence is stage-only first: run `pnputil /add-driver <inf-path>`
without `/install`, reboot, capture a baseline CSV, verify no BSOD, then install in
a subsequent session. A system restore point must be created before each medium-risk
or high-risk driver phase.

### Safe install order

The order in which drivers are installed matters. The following sequence was validated
across the sessions documented in [`SESSION_LOG.md`](SESSION_LOG.md):

1. `qcpep` (thermal/policy engine) — stage-only, reboot, verify
2. `qcsmmu` (IOMMU) — stage-only, reboot, verify
3. `qcscm` (secure channel manager) — stage-only, reboot, verify
4. `qcPILC` / `qcPILFC` (PIL and PIL filter) — install, reboot
5. `qcsubsys` (subsystem manager) — install, reboot
6. PMIC drivers (`qcpmicapps`, `qcpmicglink`) — install, reboot
7. `qcGLINK`, `qcIPCR`, `qcIPCC`, `qcqsap`, `qcTFTP`, `qcsyscache` — install, reboot
8. At this point, the ACPI deadlock must be broken before any further subsystem
   drivers can be activated

### Driver sources

Two packages cover all drivers relevant to the A14-11M:

- Acer OEM package `Base Driver_Qualcomm_0.7700.1_W11ARM64_A` — the primary source,
  downloaded from the Acer support page for SKU NX.JP3ED.002.
- WOA-Project Qualcomm Reference Drivers (`8380_CRD/200.0.57.0/`) — WHQL-signed
  reference drivers maintained at
  https://github.com/WOA-Project/Qualcomm-Reference-Drivers. Used where the OEM
  package lacks a hardware-ID match or where the WOA version is newer.

Every INF must be verified for hardware-ID match before installation.
Authenticode signature verification (`Get-AuthenticodeSignature`) is required for any
driver sourced outside the OEM package.

For the complete HWID-to-INF mapping for every failing device, see
[`Driver_Reference_Map.md`](Driver_Reference_Map.md). For the phase-by-phase install
commands and outcomes, see [`SESSION_LOG.md`](SESSION_LOG.md).

### The boundary

Beyond the components listed above, recovery is blocked. The blocker is not a missing
driver binary — the relevant INFs are staged and present in the driver store. The
blocker is a firmware-level circular dependency in the ACPI tables that prevents the
PnP manager from ever presenting the key device to the driver stack. That dependency
is examined in §6.

---

## §6 — Finding 2: The circular ACPI `_DEP` deadlock — the root cause

### Overview

The **major Qualcomm subsystem cascade** on the Acer A14-11M traces to a single
circular dependency embedded in the DSDT shipped with the Insyde H2O firmware. The
dependency forms a loop that Windows cannot resolve, blocking a critical security
platform driver (`qcsp.sys`) from ever loading. Because that driver publishes an
interface (PIL TZ) that several subsystem drivers require, the loop propagates into
the ADSP/CDSP/SPSS subsystems and, through them, the audio, compute, thermal-policy,
GPU, and Bluetooth-radio stacks that depend on those subsystems.

> **Scope of this claim.** What is established here is that the QCSP/SPSS deadlock
> blocks the subsystem cascade above. A number of *secondary* device failures —
> e.g. the ADC (`QCOM0C11`), UART bus device (`QCOM0C16`), Human Presence Sensor
> (`QCOM06D9`), EVA (`QCOM0CF1`), ISP Camera Platform (`QCOM0C32`), and HID Button
> (`ACPI0011`) — are listed in [`Driver_Reference_Map.md`](Driver_Reference_Map.md)
> as still failing or "needs investigation." These are **not yet proven to be
> downstream** of the QCSP/SPSS deadlock; some may have independent causes. Which of
> them resolve once the deadlock is broken cannot be determined until the deadlock is
> actually broken. See [§6 Limitations](#limitations-and-proof-status) below.

### The DSDT structure

The ACPI Differentiated System Description Table (DSDT) for this board is stored at:

```
HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000
```

Within the DSDT, the QCSP device is defined as:

```
Device (QCSP) {
    Name (_HID, "QCOM0C87")
    Name (_STA, 0x0F)
    Name (_DEP, Package() { \_SB.GLNK, \_SB.SOCP, \_SB.SPSS })
}
```

The `_DEP` (dependency) list declares that the QCSP device — hardware ID `QCOM0C87`,
serviced by `qcsp.sys` — must not be presented to the PnP manager until three
objects are ready: `\_SB.GLNK` (GLINK), `\_SB.SOCP`, and `\_SB.SPSS`.

### How the deadlock forms — step by step

**Step 1: GLNK and SOCP resolve.**
`\_SB.GLNK` (`ACPI\QCOM0C84`, serviced by `qcglink.sys`) and `\_SB.SOCP` both start
successfully. Two of the three `_DEP` entries are satisfied.

**Step 2: SPSS cannot start.**
`\_SB.SPSS` is hardware ID `ACPI\QCOM0C8D`, the Qualcomm Secure Processor Subsystem.
Its driver (`qcsubsys8380.inf` → `oem70.inf`) calls `AddDevice` successfully but
fails at runtime with `CM_PROB_FAILED_ADD` (NTSTATUS `0xC000003B`,
`STATUS_OBJECT_NAME_NOT_FOUND`). The most probable cause is that `qcsubsys.sys`
attempts to open the PIL TZ device interface during initialization, and that
interface is not present.

> **This link is inferred, not proven.** That `qcsubsys.sys` specifically opens the
> PIL TZ interface during init is inferred from the `STATUS_OBJECT_NAME_NOT_FOUND`
> status code and its correlation with the blank PIL TZ `Linked` value — not from
> driver symbols, a disassembly of `qcsubsys.sys`, or an ETW/WinDbg trace. It is
> highly plausible for a Qualcomm 8380 CRD board, but a reader should treat it as a
> strongly-supported hypothesis rather than a verified fact.

**Step 3: PIL TZ is the missing link.**
The PIL TZ device interface is identified by the GUID
`{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`. Its presence is visible in the registry at:

```
HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\
    {E2EB84C1-4068-4994-A48F-F3AC0D38DC29}\#
```

When active, the `Linked` value under the `#` subkey is `1`. On a broken system, the
subkey is absent or `Linked` is blank. This interface is published by `qcsp.sys`,
the driver for the QCSP device (`ACPI\QCOM0C87`).

**Step 4: `qcsp.sys` cannot load — QCSP is never presented.**
`qcsp.sys` is staged and present in the driver store (as both `oem102.inf` from the
Acer OEM package at version 1.0.4196.6900, and `oem103.inf` from WOA-Project at
version 1.0.4478.2200). However, the Windows PnP manager holds back any device whose
`_DEP` entries are not satisfied. Because `\_SB.SPSS` has failed, its `_DEP`
obligation remains unsatisfied. The PnP manager therefore never presents `ACPI\QCOM0C87`
to the device stack. `qcsp.sys` never loads.

**Step 5: The loop closes.**
Because `qcsp.sys` never loads, the PIL TZ interface is never published. Because the
PIL TZ interface is never published, SPSS `AddDevice` fails. Because SPSS has failed,
the `_DEP` on `\_SB.SPSS` in QCSP's definition remains unsatisfied. Because that `_DEP`
is unsatisfied, QCSP is never presented. The cycle is complete and self-sustaining.
No sequence of driver installs or service restarts can break it from within Windows.

### The diagnostic oracle

The byte sequence at DSDT offset `0x36C69` through `0x36C6C` provides an unambiguous
signal of the DSDT state, independent of PnP or service state:

- `53 50 53 53` (ASCII "SPSS") — DSDT is in the original, broken configuration
- `47 4C 4E 4B` (ASCII "GLNK") — the `_DEP[2]` reference has been patched from SPSS
  to GLNK, which is already satisfied; deadlock is broken

This oracle is verified by reading the raw bytes of the DSDT registry value at the
path above. The offset `0x36C69` was identified by disassembling the DSDT with
`iasl.exe -d` and locating the `_DEP` package for the QCSP object.

The same DSDT registry read served as the canary in Attempt 5m (§8,
[`ATTEMPTS.md`](ATTEMPTS.md), [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md)):
a known pattern was written to the benign CreatorRevision field at `DSDT[0x20..0x23]`
after an `EFI_MEMORY_ATTRIBUTE_PROTOCOL` unprotect attempt to distinguish whether
that protocol is absent from present-but-blocked. The pattern never appeared in the
registry, confirming the write was silently dropped.

### The failure cascade

The deadlock at QCSP/SPSS propagates into at least 25 devices across the platform:

**Subsystem failures (`CM_PROB_FAILED_ADD`):**

| Hardware ID | Friendly name | NTSTATUS |
|---|---|---|
| `ACPI\QCOM0C1B` | Qualcomm Audio DSP Subsystem (ADSP) | `0xC0000182` |
| `ACPI\QCOM0CB0` | Qualcomm Compute DSP Subsystem (CDSP) | `0xC000003B` |
| `ACPI\QCOM0C8D` | Qualcomm Secure Processor Subsystem (SPSS) | `0xC000003B` |

**QCPEP thermal and policy cluster (`STATUS_NO_SUCH_DEVICE`, 17 devices):**

| Hardware ID | Friendly name |
|---|---|
| `ACPI\QCOM0C5A` | Qualcomm Temperature Sensor |
| `ACPI\QCOM0D05` | Qualcomm Fan EC Interface |
| `ACPI\QCOM0CBF\1` | Qualcomm Temperature Sensor |
| `ACPI\QCOM0C91\0` | Qualcomm Temperature Sensor |
| `ACPI\QCOM0C58\0`, `\1` | Qualcomm Temperature Sensor |
| `ACPI\QCOM0C59\0`, `\1` | Qualcomm Temperature Sensor |
| `ACPI\VEN_QCOM&DEV_0CF2` through `0CFC` | CPU/GPU/NPU/WLAN/Modem Policy Devices |

**Cascading failures:**
- Bluetooth radio (`ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CRD08380`) — transport layer
  (`qcbtacx`) is installed and running, but the radio device is not enumerated
- Audio — fully blocked by ADSP failure; `qcasd`, `qcaucd`, and `qcaudminiport`
  drivers cannot be activated
- Adreno GPU (`ACPI\VEN_QCOM&DEV_0D17`) — failing
- Battery reporting — blocked

### Breaking the deadlock

Two structural approaches exist:

**(a) Stub SSDT injection.** Inject a supplementary SSDT that defines a new device
`\_SB.QSP0` with `_HID = "QCOM0C87"` and no `_DEP`. Windows PnP will present
`ACPI\QCOM0C87` from this stub definition without waiting for SPSS. `qcsp.sys` loads,
the PIL TZ interface activates, SPSS `AddDevice` succeeds, and the original
`\_SB.QCSP` (with its `_DEP` now satisfied) also starts. The SSDT for this purpose
is compiled and available at `efi-injection/ssdt_qcsp.aml` (80 bytes).

**(b) DSDT `_DEP` patch.** Modify the DSDT in-place, replacing the `SPSS` name
reference at byte offset `0x36C69` with `GLNK` (`47 4C 4E 4B`). This eliminates the
problematic dependency at source. Both `qcsp.sys` and SPSS can then start in sequence.

Both approaches require modifying or replacing ACPI table content before the Windows
bootloader reads it. Every mechanism for achieving this on Windows ARM64 / Insyde H2O
V1.09 has been attempted and the results are examined in §7.

### Limitations and proof status

This root-cause model is **strongly indicated by correlated evidence, including a
direct device-property record of the dependency relationship, but not proven to
kernel-debugger standard.** To keep the claim honest, the table below separates what
is established from what is inferred.

| Element | Status | Basis |
|---|---|---|
| QCSP (`QCOM0C87`) is absent from PnP; SPSS (`QCOM0C8D`) fails `CM_PROB_FAILED_ADD`; PIL TZ `Linked` is blank | **Established** | Direct registry / `Get-PnpDevice` observation, reproducible (re-confirmed Session 49, 2026-06-08) |
| The DSDT defines QCSP with `_DEP` on `\_SB.GLNK`, `\_SB.SOCP`, `\_SB.SPSS` | **Established** | Read from the live DSDT and disassembly (`iasl -d`) |
| ACPI `_DEP` informs OSPM device start-ordering | **Established** | ACPI specification |
| Windows' PnP property database records `\_SB.QCSP` as a `DependencyDependent` of SPSS (`ACPI\QCOM0C8D`), using the ACPI namespace path format that distinguishes never-presented devices from presented-but-failed ones | **Established** | `DEVPKEY_Device_DependencyDependents` on ACPI\QCOM0C8D = `\_SB.QCSP` (ACPI namespace path). Contrast: GLNK (running, OK) lists 9 dependents — all as PnP instance IDs, including SPSS itself (`ACPI\QCOM0C8D\2&daba3ff&0`) even though SPSS later failed AddDevice, because SPSS *was* presented to PnP. QCSP does not appear in GLNK's list. SOCP (running, OK) has no `DependencyDependents` at all. Only SPSS (failed) retains `\_SB.QCSP` as an ACPI path — the format used when a device was never presented to the PnP manager. (Sessions 49–50, 2026-06-08) |
| `ACPI\QCOM0C87` was never presented to the PnP manager as an ACPI device | **Established** | Kernel-PnP/Configuration log (732 events, all boots): zero events for `ACPI\QCOM0C87`; setupapi.dev.log: no entry for `ACPI\QCOM0C87` as a hardware-initiated device install; `HKLM\...\Enum\ACPI` has no QCOM0C87 subkey (Session 49, 2026-06-08) |
| Windows holds `ACPI\QCOM0C87` back *because* `\_SB.SPSS` is unresolved | **Strongly indicated, with new live in-memory corroboration — acpi.sys decision itself still not directly captured** | SPSS failed; Windows' dependency database records QCSP as SPSS's dependent; QCSP never appeared in any PnP or event log; consistent with ACPI spec `_DEP` gating behavior. A full-boot WPR/ETW trace with `Kernel-Acpi`, `ACPI Driver Trace Provider`, `Kernel-PnP`, and `Kernel-Boot` enabled captured **zero events from any of the four** during the failure window (Session 50, 2026-06-08) — confirming the acpi.sys `_DEP`-gate decision is not observable via ETW on this system, not merely "not yet captured." Local kernel debugging (Session 51, 2026-06-08) then directly inspected the live SPSS device object in kernel memory and found `ExtensionFlags = DOE_START_PENDING` — a first-hand, in-memory observation that the device's start is being held pending right now, exactly as the model predicts (rather than an after-the-fact log record of a past decision). It does not, by itself, name *which* dependency is doing the gating — that would require locating the in-memory `_DEP`/QCSP-naming structure, which a small-window kernel-memory string search for `QCOM0C87`/`QCSP`/`\_SB.QCSP` did not find (see §11) |
| `qcsubsys.sys` fails because it opens the (absent) PIL TZ interface during init | **Inferred** | NTSTATUS `STATUS_OBJECT_NAME_NOT_FOUND` + correlation; not from driver symbols or a trace |
| Patching `_DEP[2]` SPSS→GLNK would break the deadlock | **Inferred — raw-AML live patch tested and insufficient; UEFI-time fix untested with correct MAP GUID** | Session 52 (2026-06-09): DSDT pool copy at physical `0xD4781018` located, `53 50 53 53` ("SPSS") confirmed at offset `0x36C69`, physical write succeeded (bytes changed to "GLNK"), checksum fixed. `pnputil /scan-devices` rescan: all three oracles unchanged. Result: `acpi.sys` uses a pre-parsed namespace cache for `_DEP` — raw AML bytes are read once at boot and not re-interpreted on rescan. The UEFI-time fix (D8: MAP unprotect + DSDT patch before `ExitBootServices`) and a boot-time kernel-driver interception remain untested. |

**What would turn "Windows holds QCSP because SPSS is unresolved" from strongly
indicated into proven** — still not done, still recorded as open paths in
[§11](#11--open-questions-untried-and-unproven-paths):

- ~~A **WPR / ETW boot trace**~~ — **attempted and closed (Session 50, 2026-06-08).**
  A five-provider boot-trace profile (`Kernel-Acpi`, `ACPI Driver Trace Provider`,
  `Kernel-PnP`, `Kernel-Boot`, `DriverFrameworks-UserMode`) captured a full reboot
  through the failure state. The four ACPI/PnP/Boot providers logged **zero events**
  — confirmed as a real negative result (the fifth provider, `DriverFrameworks-UserMode`,
  *did* log real events for unrelated devices in the same capture, proving the profile
  was honored). This closes the ETW path: `acpi.sys`'s `_DEP`-gate decision is not
  instrumented for ETW on this system, so no boot trace can promote this row to
  "proven." See SESSION_LOG Session 50 for the full analysis.
- ~~A **live local-kernel-debugger inspection**~~ — **attempted, partially successful,
  brute-force variant closed (Session 51, 2026-06-08).** With `bcdedit /debug on` and
  `kdARM64.exe -kl`, the live SPSS device object was located and inspected directly:
  `ExtensionFlags = DOE_START_PENDING` (first-hand confirmation the start is being
  held pending) and `Problem Status 0xc000003b` decoded to the more specific
  `STATUS_OBJECT_PATH_COMPONENT_NOT_A_DIRECTORY` (a new clue — see §11). However, a
  full-address-space `s -a`/`s -u` string search for `QCOM0C87`/`QCSP`/`\_SB.QCSP`
  (the search that could locate the in-memory `_DEP` structure and complete the proof)
  is **not practically achievable**: every attempt at a wide range (32 MB, 2 GB)
  hung indefinitely and had to be force-killed, while a small 2 MB window around
  `acpi.sys`'s code returned a clean negative. This closes the brute-force variant of
  the live-memory path — mirroring the Session 50 ETW conclusion, a different
  instrumentation layer hits the same kind of wall. The avenue is *narrowed, not
  closed*: a future session could still try other small, well-chosen windows (e.g.
  around `qcsubsys8380.sys` pool allocations or PnP-manager structures) if their
  addresses can be obtained without triggering the `lm`/symbol-resolution hang. See
  SESSION_LOG Session 51 for the full analysis.
- ~~A **live-kernel raw-AML DSDT patch** (SPSS→GLNK at `0x36C69`) followed by a
  forced bus rescan~~ — **attempted, insufficient (Session 52, 2026-06-09).** The DSDT
  pool copy at physical `0xD4781018` was located, bytes confirmed, write succeeded.
  Rescan oracle: unchanged. `acpi.sys` uses a pre-parsed namespace cache — raw AML
  patches after boot have no effect on `_DEP` evaluation. Boot-time interception or
  UEFI-time fix (D8, correct MAP GUID) remain open. See SESSION_LOG Session 52.
- A **factory-image comparison** establishing whether a working A14-11M uses the same
  DSDT (firmware bug confirmed) or a different provisioning/order (software-side cause).

---

## §7 — Finding 3: Why every standard ACPI override mechanism is dead on Windows ARM64

### Context

The four mechanisms below represent the complete set of standard and semi-standard
ACPI table override paths available to a Windows user without firmware-level access.
Each was tested on the Acer A14-11M (Insyde H2O V1.09, Secure Boot OFF, HVCI ON,
Windows 11 ARM64 build 26200). None succeeded. This section documents the precise
reason each fails so that future investigators do not repeat the same work.

The underlying architectural fact common to mechanisms 1–3 is that Windows ARM64's
bootloader (`winload.efi`) reads ACPI tables exclusively from the UEFI firmware's
`EFI_ACPI_TABLE_PROTOCOL`, as exposed through the EFI System Table's
`ConfigurationTable` array. This is fundamentally different from the x86/BIOS path,
where the bootloader also honors the `HKLM\SYSTEM\CurrentControlSet\Control\acpitables`
registry key and the `ACPIOVERRIDETEST` BCD option. Those x86 mechanisms do not exist
in the ARM64 code path.

---

### Mechanism 1 — `HKLM\...\acpitables` registry key and `ACPIOVERRIDETEST` BCD flag

**How it is supposed to work (x86/x64):** The Windows x86/x64 bootloader checks
`HKLM\SYSTEM\CurrentControlSet\Control\acpitables` for binary ACPI table overrides.
Setting the BCD option `loadoptions ACPIOVERRIDETEST` activates this check. An SSDT
placed at `acpitables\00000000` is merged into the ACPI table set before Windows
reads them.

**Why it fails on ARM64:** The ARM64 `winload.efi` does not implement this code
path. The registry key is read by x86/x64-specific boot logic that is absent in the
ARM64 binary. The `ACPIOVERRIDETEST` flag is similarly x86/x64-only.

**Test result (Attempt 1, Sessions 16–17):** An SSDT containing a test device with
`_HID = "QCOM1234"` was written to `acpitables\00000000`. The BCD loadoptions flag
was set. After multiple reboots, `ACPI\QCOM1234` never appeared in Device Manager.
The live DSDT bytes at offset `0x36C69` remained `53 50 53 53` ("SPSS"), confirming
the override had no effect. Result: dead on ARM64.

---

### Mechanism 2 — SSDT files placed in the EFI System Partition

**How it is supposed to work (some UEFI implementations):** Some UEFI firmware
implementations scan specific ESP paths at boot and load any SSDT files found there,
merging them into the live ACPI table set before the OS bootloader starts. Common
paths tested include `S:\EFI\ACPI\`, `S:\EFI\OEM\`, `S:\acpi\`, and
`S:\EFI\ACPI\SSDT.aml`.

**Why it fails on this board:** The Insyde H2O firmware on the Acer A14-11M
(NX.JP3ED.002, V1.09) does not implement ESP SSDT loading. Whether this is a
deliberate omission or an Insyde configuration choice is not known from the evidence
gathered, but the behavior is unambiguous.

**Test result (Attempt 2, Session 17):** The same `QCOM1234` test SSDT was placed
at all four candidate ESP paths. After rebooting, `ACPI\QCOM1234` never appeared.
Result: dead on this firmware.

---

### Mechanism 3 — Binary-patched DSDT loaded via `acpitables` registry

**How it is supposed to work:** Instead of injecting a new SSDT, the full DSDT is
extracted, binary-patched (replacing the SPSS name bytes at offset `0x36C69` with
GLNK bytes `47 4C 4E 4B`), and placed in `acpitables\00000000` as a complete DSDT
replacement. On x86/x64 with the ACPIOVERRIDETEST flag, this replaces the firmware
DSDT.

**Why it fails on ARM64:** Identical to Mechanism 1. The registry key is ignored by
`winload.efi` on ARM64, regardless of the content of the value (SSDT or patched DSDT).

**Test result (Attempt 3, Sessions 22–23):** Secure Boot was disabled for this test.
The 279,633-byte DSDT was extracted, patched at offset `0x36C69` (confirmed byte
change: `53 50 53 53` → `47 4C 4E 4B`), and written to `acpitables\00000000`. After
reboot, reading the live DSDT from
`HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000` still returned `53 50 53 53`
at offset `0x36C69`. The Windows-visible DSDT was unchanged. Result: dead on ARM64.

---

### Mechanism 4 — GRUB2 `acpi` module with chainloader

**How it is supposed to work:** GRUB2 includes an `acpi` module that, when combined
with the `acpi /path/to/ssdt.aml` command in `grub.cfg`, loads the AML file into
memory and appends a pointer to it in the XSDT (Extended System Description Table).
The theory is that when the GRUB chainloader then hands off to `bootmgfw.efi`, Windows
will find the modified XSDT and parse the injected SSDT.

**Why it fails on ARM64:** GRUB2's `acpi` module modifies the XSDT in RAM but does
not update the `RSDP->XsdtAddress` field in the EFI ConfigurationTable entry. The
Windows ARM64 bootloader locates the ACPI 2.0 table set by walking the EFI System
Table's `ConfigurationTable` array, finding the entry with GUID
`{8868E871-E4F1-11D3-BC22-0080C73C8881}` (ACPI 2.0), and reading the RSDP pointer
from that entry. Because GRUB does not update this pointer, `winload.efi` finds the
original firmware RSDP and reads the original, unmodified XSDT.

**Test result (Attempt 4, Sessions 23–25):** A GRUB2 USB was prepared with
`grubaa64.efi` (Ubuntu ARM64 build), the `acpi` and `chain` modules, and a `grub.cfg`
loading the `QCOM0C87` stub SSDT and chainloading `bootmgfw.efi`. GRUB menu appeared
and Windows booted normally. `ACPI\QCOM0C87` never appeared in Device Manager. The
DSDT oracle at `0x36C69` remained unchanged. Result: dead on ARM64 — GRUB's XSDT
modification is invisible to the Windows ARM64 bootloader.

---

### Summary

All four standard mechanisms are dead on Windows ARM64 / Insyde H2O V1.09. The
failure mode of mechanisms 1, 2, and 3 is architectural: ARM64 `winload.efi` has no
code path that reads from `acpitables`, BCD flags, or ESP-based SSDT files. The
failure mode of mechanism 4 is a gap in GRUB's implementation: it modifies the XSDT
in RAM without updating the EFI ConfigurationTable RSDP pointer that `winload.efi`
actually follows.

The only remaining software path is a custom UEFI application that calls
`EFI_ACPI_TABLE_PROTOCOL->InstallAcpiTable()` before `ExitBootServices()`, or that
patches ACPI memory directly using `EFI_MEMORY_ATTRIBUTE_PROTOCOL` to clear write
protection before modifying the live DSDT. Both of these paths were pursued in a
series of fifteen sub-attempts (5a through 5o) and encountered a further set of
platform-specific blockers. Those attempts are examined in §8.

---

## §8 — Finding 4: UEFI injection — every software path blocked

After the four standard mechanisms failed, the only remaining software path was a
custom UEFI application — `AcpiInject.efi` — built as a PE32+ AARCH64 binary by a
Python assembler (`build_efi.py`, using `keystone-engine`). The original plan: call
`BootServices->LocateProtocol()` to obtain `EFI_ACPI_TABLE_PROTOCOL`, call
`InstallAcpiTable()` with an 80-byte stub SSDT that creates `\_SB.QSP0` with
`_HID = "QCOM0C87"` and no `_DEP`, then chainload `bootmgfw.efi`. Fifteen
sub-attempts (5a through 5o) document a progressive uncovering of platform-specific
blockers — each attempt narrowed the cause to the next protection layer. Full
chronological detail is in [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md);
this section narrates the sequence.

### 5a — GRUB chainloader to AcpiInject.efi (Session 30)

The first deployment used Ubuntu Shim to chainload `AcpiInject.efi` through GRUB.
Shim's `EFI_SECURITY_ARCH_PROTOCOL` hook intercepted `LoadImage` and rejected the
unsigned binary. Result: failed at load time, no execution.

### 5b — Direct BOOTAA64.EFI to bypass Shim (Session 31)

`AcpiInject.efi` was deployed directly as `D:\EFI\BOOT\BOOTAA64.EFI` on the USB,
bypassing Shim. The binary loaded but faulted on the first global-variable write.
Cause: the PE `.text` section had `MEM_EXECUTE | MEM_READ` but not `MEM_WRITE`, so
ARM64 raised a permission fault on store instructions to in-binary data.

### 5c — Added MEM_WRITE + ConOut debug output (Sessions 32–33)

The PE section flags were corrected and `ConOut` print calls were added to dump
progress. No output appeared. The Tiano PE loader silently rejected the binary
because two PE header fields were invalid: `NumberOfRvaAndSizes = 0` (should be 16)
and `DllCharacteristics = 0x0000` (should include `NX_COMPAT`, e.g. `0x0100`).

### 5d — Fixed PE headers and added `.reloc` section (Sessions 33–34)

Headers set to `NumberOfRvaAndSizes = 16`, `DllCharacteristics = 0x0100`. A `.reloc`
section was added. The binary now ran — but the log file the application tried to
create never appeared. Cause: wrong `EFI_FILE_PROTOCOL` function-pointer offsets in
the assembled code. `Delete` was being called at the offset where `Write` should
have been.

### 5e — Fixed EFI_FILE_PROTOCOL offsets (Sessions 34–35)

`Write` was corrected to offset `+40`, `Flush` to offset `+80`. The log file still
did not appear.

### 5f — Brute-force SFS scan; removed marker check (Sessions 35–36)

The application was rewritten to enumerate every SFS volume on every handle and
attempt to create the log on the first writable one. The USB SFS handle was not
returned by `LocateHandleBuffer(ByProtocol, SFS_GUID)` on this firmware at all.

### 5g — Try first NVMe SFS handle (Sessions 36–37)

The NVMe ESP SFS is enumerated, but `Open(CREATE)` from a UEFI application context
returns failure. No file logging channel is available at all.

### 5h — UEFI NVRAM variable logging via `SetVariable` (Sessions 37–38)

`AcpiInject.efi` was rewritten to log via `RuntimeServices->SetVariable()` instead
of a file. Reading back from Windows, `GetFirmwareEnvironmentVariableW` returns
error 1314 (`ERROR_PRIVILEGE_NOT_HELD`) for the AcpiLog variable — and for *every*
other variable tested, including the standard `BootOrder`
(GUID `{8BE4DF61-93CA-11D2-AA0D-00E098032B8C}`). `SeSystemEnvironmentPrivilege` is
present in the elevated token and `AdjustTokenPrivileges` succeeds; the block is
not at the Windows privilege layer. The firmware-side runtime variable services are
either unimplemented or blocked outside SMM. The NVRAM logging channel is
permanently dead.

At this point, after seven sub-attempts producing no observable output, the
`EFI_ACPI_TABLE_PROTOCOL` path was concluded exhausted: the protocol is either
absent on this Insyde build or its `InstallAcpiTable()` call rejects the table.
There is no UEFI-side diagnostic mechanism on this firmware to determine which.

### The wrong-GUID bug (covers 5a–5g)

A retrospective audit of `build_efi.py` against `EFI_Injection_Tracking.md` found
that the `ACPI_GUID` constant embedded in the binary was incorrect across all
builds through 5g:

```
WRONG (used by build_efi.py):  {8D59D32B-C655-4AE9-9B15-F25904992A43}
                               (= EFI_ABSOLUTE_POINTER_PROTOCOL)
CORRECT for ACPI injection:    {FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}
                               (= EFI_ACPI_TABLE_PROTOCOL)
```

This means that even if `EFI_ACPI_TABLE_PROTOCOL` had been present on the firmware,
the code in 5a–5g would not have located it. `LocateProtocol` either returned
failure (and the code silently skipped injection) or located the unrelated Absolute
Pointer protocol and invoked the wrong function pointer as `InstallAcpiTable()`.
Either outcome explains why no injection observably occurred in 5a–5g — and means
the conclusion at the end of 5h ("`EFI_ACPI_TABLE_PROTOCOL` is absent or rejects
the table") is not strictly proven by 5a–5g alone. The GUID was corrected before
5h, but by then no working diagnostic channel remained to confirm the protocol's
behavior. Full audit in [`AcpiInject_Findings.md`](AcpiInject_Findings.md).

### 5i — Direct XSDT modification (Sessions 38–39)

With `EFI_ACPI_TABLE_PROTOCOL` no longer trusted as a path, the strategy shifted to
direct ACPI table chain modification. The application walked
`SystemTable->ConfigurationTable`, found the entry with the ACPI 2.0 GUID
`{8868E871-E4F1-11D3-BC22-0080C73C8881}`, followed it to RSDP, allocated a new XSDT
in `EfiACPIMemoryNVS`, copied the old XSDT, appended a pointer to the SSDT,
recalculated the XSDT checksum, and wrote the new XSDT address into
`RSDP->XsdtAddress` with checksum fix-up. After reboot:
`HKLM\HARDWARE\ACPI\SSDT` showed no new key. The SSDT had not been parsed. Cause:
the RSDP pointer write was silently dropped. RSDP resides in firmware-managed
read-only memory; the firmware does not raise a fault on writes to that region —
it ignores them.

### 5j — SSDT data also in `EfiACPIMemoryNVS` (Sessions 39–40)

The SSDT data had originally been embedded in the binary's `.text` (EfiLoaderCode).
5j placed the SSDT bytes in `EfiACPIMemoryNVS` to rule out memory-type rejection by
Windows. The RSDP write still failed silently; same outcome as 5i.

### 5k — DSDT in-place byte patch at offset 0x36C69 (Session 40)

If RSDP cannot be modified to point to a new XSDT, the alternative is to patch the
existing DSDT in place: change the QCSP `_DEP[2]` name field at offset `0x36C69`
from `53 50 53 53` ("SPSS") to `47 4C 4E 4B` ("GLNK"), then recalculate the DSDT
checksum. After reboot, the live DSDT at
`HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000` still reads
`53 50 53 53` at offset `0x36C69`. DSDT pages are write-protected on the same
basis as RSDP.

### 5l — `EFI_MEMORY_ATTRIBUTE_PROTOCOL` unprotect then patch (Sessions 40–41) — **INVALID: wrong GUID**

> **Audit note (2026-06-09):** The GUID used in this attempt was
> `{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}`, which is **`EFI_COMPONENT_NAME2_PROTOCOL`**
> — not `EFI_MEMORY_ATTRIBUTE_PROTOCOL`. The correct MAP GUID is
> `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}` (verified against EDK2 master
> `MdePkg/Include/Protocol/MemoryAttribute.h`). Because `EFI_COMPONENT_NAME2_PROTOCOL`
> is essentially always registered, `LocateProtocol` most likely succeeded and the code
> called that protocol's vtable at MAP's function offsets — invoking an unrelated
> function, not `ClearMemoryAttributes()`. This is the same class of error as the
> already-documented 5a–5g wrong-GUID bug. **The results of 5l and 5m are invalid;
> `EFI_MEMORY_ATTRIBUTE_PROTOCOL` was never actually invoked.** The GUID is corrected
> in `build_efi.py` as of 2026-06-09; a proper retest (Attempt D8) remains to be done.

UEFI 2.10 introduced `EFI_MEMORY_ATTRIBUTE_PROTOCOL`
(correct GUID `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}`), which exposes
`ClearMemoryAttributes()` to remove `EFI_MEMORY_RO` from specific pages. 5l attempted
to call `LocateProtocol` to obtain MAP, clear the read-only attribute on the DSDT pages,
then issue the same byte patch as 5k. The DSDT remained unchanged — but as noted above,
this result is invalid because the wrong protocol was located.

### 5m — MAP canary write to localise the block (Sessions 46–47) — **INVALID: wrong GUID (same as 5l)**

> **Audit note (2026-06-09):** Same wrong-GUID bug as 5l applies here. The canary result
> (bytes unchanged after stall) does **not** establish that MAP is absent or that
> `ClearMemoryAttributes()` is non-functional — it only establishes that calling
> `EFI_COMPONENT_NAME2_PROTOCOL`'s vtable at MAP's offsets did not unprotect the DSDT.
> The conclusion "direct DSDT-write path is permanently closed" is **not supported**
> by 5m's evidence and must be re-derived with the correct GUID (see Attempt D8 in
> NEXT_STEPS_PostReview_2026-06-09.md).

Attempt 5l could not distinguish whether MAP was absent or present-but-ineffective. 5m
added a canary to separate the two cases: after the (invalid) MAP call, the application
wrote a known four-byte pattern to `DSDT[0x20..0x23]` (CreatorRevision) and added a
visible multi-second stall. The canary bytes read `00 00 00 05` — unchanged — and the
stall was observed, confirming the application ran to that point. The original conclusion
("writes silently dropped even after MAP unprotect") is not supported given the GUID bug;
the direct DSDT-write path is **not yet proven permanently closed**.

### 5n — `BootServices->InstallConfigurationTable()` (Sessions 47–48)

Rather than write to protected memory at all, 5n called the firmware's own
service to swap the ACPI table set. The application walked
`SystemTable->ConfigurationTable`, read the existing RSDP (read-only), allocated
four pages of `EfiACPIMemoryNVS`, built a fresh RSDP → XSDT → SSDT chain in that
writable memory (a new XSDT with the 80-byte QCSP stub appended and all checksums
recomputed), and called `InstallConfigurationTable(&ACPI_20_GUID, new_rsdp)` to
repoint the ACPI 2.0 ConfigurationTable entry at the new chain before chainloading
`bootmgfw.efi`. After reboot, `HKLM\HARDWARE\ACPI\SSDT` contained only the
firmware's own `Compal` key — no `QCOMM_` key. The SSDT was not parsed and the
deadlock was not broken.

A retrospective audit of this build found that its visual-stall routine used the
wrong vtable offset — 232 (`ExitBootServices`) instead of 248 (`Stall`) — so the
intended on-screen pause was a no-op. This bug affected only the diagnostic
stall, not the `InstallConfigurationTable` call itself (which used the correct
offset 192). It does, however, mean 5n produced no trustworthy on-screen
confirmation of its own execution, which motivated 5o.

### 5o — `InstallConfigurationTable()` with on-screen ICT/CT diagnostics (Session 48)

Because 5n produced no observable signal beyond "only Compal," 5o rebuilt the
same `InstallConfigurationTable()` logic as a pure diagnostic — its purpose was
to determine *why* 5n failed, not to try a new mechanism. Two `ConOut` strings
were printed before a corrected 8-second `Stall`: `[AI] ICT=OK` / `ICT=ERR` (the
status returned by the `InstallConfigurationTable` call) and `[AI] CT=OURS` /
`CT=OLD` / `CT=NONE` (whether a re-scan of the ConfigurationTable found the new
RSDP after the call).

**Result:** the boot test was run and **failed**. `HKLM\HARDWARE\ACPI\SSDT` again
showed only the `Compal` key, `ACPI\QCOM0C87` did not appear in PnP, and the
deadlock was not broken. With 5o, the `InstallConfigurationTable()` path joins
every other in-band software mechanism as closed on this firmware: the firmware's
own configuration-table service does not result in Windows parsing the replacement
ACPI chain.

### Summary of §8

Across fifteen sub-attempts (5a–5o), no software-only ACPI table modification
succeeded. Each failure narrowed the cause to a deeper protection layer: file I/O
blocked, then NVRAM blocked, then `EFI_ACPI_TABLE_PROTOCOL` not usable, then RSDP
read-only, then DSDT read-only, then `EFI_MEMORY_ATTRIBUTE_PROTOCOL`
non-functional, and finally — with 5n/5o — the firmware's own
`InstallConfigurationTable()` service producing no parsed table in Windows. Every
in-band path a UEFI application can take to alter the ACPI tables Windows reads
has now been exhausted. The platform's combined protection model — what's locked
and what's blocked — is examined in §9.

---

## §9 — Finding 5: Firmware-managed read-only ACPI memory

The platform-specific finding that explains §8 is that the firmware enforces
read-only protection on the entire ACPI table chain AND blocks every diagnostic
channel that would let an EFI application probe its own state. Six facts
characterise this protection model:

1. **RSDP, XSDT, FADT, and DSDT all reside in firmware-managed pages that an EFI
   application cannot modify.** Writes do not raise an ARM64 permission fault —
   they are silently dropped. Confirmed by Attempts 5i and 5j (RSDP), 5k (DSDT),
   and 5l (DSDT after MAP unprotect attempt).

2. **`EFI_ACPI_TABLE_PROTOCOL` is either absent or its `InstallAcpiTable()`
   rejects this table.** No protocol-based injection. Confirmed by Attempt 5h —
   but, as noted in §8, the wrong-GUID bug means absence-versus-rejection cannot
   be cleanly distinguished without a working UEFI-side diagnostic channel.

3. **`EFI_MEMORY_ATTRIBUTE_PROTOCOL` (UEFI 2.10) status is unknown — not yet tested.**
   This is the standard UEFI API for changing memory page attributes. Attempts 5l and
   5m were intended to test it but used the wrong GUID
   (`{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}` = `EFI_COMPONENT_NAME2_PROTOCOL`) and
   never invoked MAP. The correct GUID is `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}`
   (EDK2 `MdePkg/Include/Protocol/MemoryAttribute.h`). The claim "MAP is absent or
   non-functional" is **not supported by the evidence**; a proper retest (Attempt D8)
   is required. The GUID has been corrected in `build_efi.py` as of 2026-06-09.

4. **UEFI runtime variable services are fully blocked from Windows.**
   `GetFirmwareEnvironmentVariableW` returns error 1314 for every variable
   tested, including standard global variables such as `BootOrder` (GUID
   `{8BE4DF61-93CA-11D2-AA0D-00E098032B8C}`). The block is on the firmware side,
   not at the Windows privilege layer (the relevant token privilege is present
   and adjusts successfully). Discovered in Attempt 5h.

5. **All SFS volumes refuse `Open(CREATE)` from UEFI application context.** The
   USB SFS handle is not returned by `LocateHandleBuffer`. The NVMe ESP SFS is
   enumerated but refuses CREATE. Discovered in Attempts 5f and 5g.

6. **`BootServices->InstallConfigurationTable()` does not result in Windows
   parsing a replacement ACPI chain.** Even when the table swap is performed
   through the firmware's own service rather than by writing protected memory —
   with a fully-formed RSDP/XSDT/SSDT chain allocated in `EfiACPIMemoryNVS` — no
   `QCOMM_` SSDT key appears in `HKLM\HARDWARE\ACPI\SSDT` after boot. Either the
   call is rejected or `winload.efi` does not honour a ConfigurationTable entry
   replaced this late. Confirmed by Attempts 5n and 5o.

No software-only ACPI table modification is possible from a UEFI application on
this firmware. The canary-write experiment (Attempt 5m) and the
`InstallConfigurationTable()` attempts (5n/5o) — the last remaining in-band
probes — have all now been run and confirm the model above. The remaining paths
are entirely out of band: a firmware update from Acer that removes SPSS from
QCSP's `_DEP`, or offline BIOS ROM modification with external tooling. These are
examined in §11.

---

## §10 — Vendor support response

### The escalation submitted to Acer

A detailed technical writeup of the bug was submitted to Acer support via the
manufacturer's standard support email channel. The writeup described the DSDT
`_DEP` chain on QCSP, the inactive PIL TZ device interface, the absence of
`ACPI\QCOM0C87` from PnP, and the resulting `CM_PROB_FAILED_ADD` failures on
ADSP, CDSP, and SPSS. The escalation identified the failure as a firmware-level
ACPI dependency-ordering issue and requested either a BIOS update that removes
SPSS from QCSP's `_DEP`, or guidance on obtaining the OEM-provisioned driver
state that is present on the device at unboxing but discarded on a clean
reinstall.

### Response timeline and content

After approximately a seven-day wait, the response was a four-line email pointing
to (a) Windows Update and (b) Acer's recovery media purchase page. No escalation
to a firmware or BIOS team was offered. No engagement with the technical content
of the submitted writeup was visible in the reply.

The reply was received on 22 May 2026, signed by an Acer support representative
("Max"). The verbatim message follows; the original language is Danish.

> Hej,
>
> Tak for din henvendelse.
>
> Prøv i første omgang at opdatere drivere direkte fra Microsoft:
>
> [https://support.microsoft.com/da-dk/windows/hent-automatisk-anbefalede-og-opdaterede-hardwaredrivere-0549a8d9-4842-8acb-75fa-a6faadb62507](https://support.microsoft.com/da-dk/windows/hent-automatisk-anbefalede-og-opdaterede-hardwaredrivere-0549a8d9-4842-8acb-75fa-a6faadb62507)
>
> Hvis det ikke løser problemet kan du bestille usb recovery på denne side.
>
> [https://store.acer.com/da-dk/e-recovery](https://store.acer.com/da-dk/e-recovery)
>
> Med venlig hilsen

English translation (for readers outside Denmark — the Danish above is the
authoritative original):

> Hi,
>
> Thank you for your inquiry.
>
> As a first step, try updating drivers directly from Microsoft:
>
> https://support.microsoft.com/.../hent-automatisk-anbefalede-og-opdaterede-hardwaredrivere-...
>
> If that does not solve the problem, you can order USB recovery from this page.
>
> https://store.acer.com/da-dk/e-recovery
>
> Best regards

### Windows Update does not address the documented bug

Windows Update does not ship Insyde firmware updates for this SKU, does not modify
firmware ACPI tables, and does not ship the OEM-provisioned driver store or the
factory image. The failure profile documented in §3 persists across Windows
Update cycles on this device.

### The recovery media probably restores the working factory state (hypothesis — untested)

The Acer-supplied recovery media is the image the device shipped with, and the device
worked at unboxing. From that, it is reasonable to *hypothesise* that the factory
state includes OEM provisioning not reproducible from the public Acer driver packages
— for example a pre-staged `qcsp.sys` activation path, or a different ACPI boot-time
ordering that does not enter the deadlock — and that a factory restore would return
the device to that working state.

> **This is a hypothesis, not a tested result.** No factory image or recovery medium
> was booted or compared against the clean-reinstall state in this work. It is equally
> possible the factory image ships the *same* DSDT and avoids the deadlock purely
> through driver-store provisioning or load order — or, less likely, that it does not
> avoid the deadlock at all. The factory-image comparison that would settle this is
> recorded as the highest-value open path in [§11](#11--open-questions-untried-and-unproven-paths).

### Why a paid recovery medium is not an acceptable remediation here

The Acer A14-11M (NX.JP3ED.002) is an actively-sold SKU under standard
manufacturer warranty. The device has no hardware defects. The customer purchased
a working Windows 11 ARM64 device. A user should be able to recover and reinstall
the operating system that shipped with their warranty-active, defect-free device
without further payment. When the only known working remediation for a documented
firmware-level bug is paywalled behind the purchase of physical recovery media
with a multi-day delivery window, the customer is required to pay — and wait —
to be restored to the working state they originally purchased.

### Case status

As of **8 June 2026**, no further communication has been received from Acer since
the single four-line reply of 22 May 2026 — a span of more than two weeks with no
follow-up, no engagement with the submitted technical evidence, and no escalation
to a firmware or BIOS team. The case has been neither formally closed nor
meaningfully progressed. The author remains willing to share the full failure
chain with anyone at Acer or Qualcomm able to act on it, and would welcome a
remediation path that does not require re-purchase of the device's shipping
software state.

---

## §11 — Open questions: untried and unproven paths

What is exhausted is **in-band ACPI table injection from a UEFI boot application**
(§7, §8): the registry/BCD override, ESP SSDTs, GRUB, the custom `AcpiInject.efi`
(5a–5o), and `InstallConfigurationTable()`. That is a narrower statement than "every
possible avenue." Several classes of approach were **not attempted** in this work —
some that would *prove or refute* the root cause, and some that might *fix or work
around* it from outside the UEFI-injection path.

Everything in this section is explicitly **untried and/or unproven.** None of it has
been executed; nothing here is a result. Items are recorded so that another
investigator (or a future session) can pick them up, and so the boundary of what this
paper actually establishes is unambiguous. Where a path rests on an assumption this
work could not verify, that is stated.

### 11a — Validation paths (would confirm or refute the root cause; do not fix it)

- **Factory-image / recovery-media comparison — highest value.** Obtain Acer recovery
  media or an untouched A14-11M factory install. *Before changing anything,* export
  the ACPI tables (`HKLM\HARDWARE\ACPI`), `DeviceClasses`, the driver store mapping,
  SetupAPI logs, and PnP state, and diff against the clean-reinstall state captured
  here. If the working image carries the **same** DSDT, the missing piece is
  provisioning / load order, not the firmware table; if the DSDT **differs**, the
  firmware-table defect is confirmed independently. *Status: not attempted — no
  factory image was booted or compared.* This also directly tests the §10 hypothesis.
- **ETW / Kernel-PnP static capture — done (Session 49, 2026-06-08).**
  The `Microsoft-Windows-Kernel-PnP/Configuration` log (732 events) and
  `setupapi.dev.log` were searched for `QCOM0C87`, `QCOM0C8D`, `_DEP`, and dependency
  keywords. Key results: (a) `ACPI\QCOM0C8D` (SPSS) has a confirmed Event 411 ("had a
  problem starting", Problem 0x1F / 0xC000003B); (b) `ACPI\QCOM0C87` produced **zero
  events** in the Kernel-PnP log and zero hardware-initiated entries in setupapi — it
  was never presented to the PnP manager; (c) `DEVPKEY_Device_DependencyDependents` on
  SPSS records `\_SB.QCSP` using the ACPI namespace path, indicating the ACPI
  enumerator populated this during `_DEP` evaluation before QCSP was ever presented.
  Raw captures in `diagnostic-captures/` (gitignored).
- **WPR / ETW boot trace — attempted and closed as a confirmed limitation (Session 50,
  2026-06-08).** A custom WPR boot-trace profile (`dep_gate_boottrace.wprp`) was armed
  with five providers — `Microsoft-Windows-Kernel-Acpi`, `ACPI Driver Trace Provider`,
  `Microsoft-Windows-Kernel-PnP`, `Microsoft-Windows-Kernel-Boot`, and
  `Microsoft-Windows-DriverFrameworks-UserMode` — across a full reboot, then captured
  with `wpr -stopboot` and analyzed with `tracerpt`. All three baseline oracles
  re-confirmed an exact match before and after, so the trace covers the persistent
  failure window being studied. Result: the four ACPI/PnP/Boot providers logged
  **zero events of any kind** (not just zero for QCSP/SPSS); only
  `DriverFrameworks-UserMode` produced events, and those were for two unrelated UMDF
  devices (`ACPI\QCOM06D8`, `ACPI\QCOM0CA8`), which proves the profile *was* honored —
  the silence from the other four is a real negative result, not a misregistration.
  This confirms `acpi.sys`'s `_DEP`-gate evaluation is **not observable via ETW** on
  this system/build through any provider available in a standard WPR boot-trace
  profile — it fires too early and/or is not instrumented. Raw `.etl`, CSV dump, and
  summary in `diagnostic-captures/` (gitignored); full analysis in SESSION_LOG Session
  50. *Status: Kernel-PnP static capture done; WPR boot trace attempted and closed —
  this avenue cannot promote the root-cause model to "proven."*
- ~~**Live-kernel raw-AML DSDT patch (fix-validation)**~~ — **attempted; raw-AML patch
  is insufficient (Session 52, 2026-06-09).** DSDT pool copy located at physical
  `0xD4781018` (Windows updates X_DSDT in FADT to point to a non-paged pool copy;
  the `+0x18` byte offset = standard pool header). `!db` confirmed `53 50 53 53`
  ("SPSS") at physical `0xD47B7C81` (= `0xD4781018 + 0x36C69`). `!eb` physical-memory
  writes succeeded — pool copy is writable. Bytes changed to "GLNK", checksum fixed.
  `pnputil /scan-devices` rescan: all three oracles unchanged (QCOM0C87 absent, QCOM0C8D
  failing, PIL TZ not linked). Conclusion: `acpi.sys` builds the ACPI namespace from
  raw AML **once at boot** and evaluates `_DEP` from the cached parsed Package object
  thereafter — not by re-reading AML bytes. A rescan does not re-parse the AML; patching
  the raw bytes after boot has no effect on device enumeration.
  The DSDT pool copy resets on reboot (volatile allocation). **What remains:**
  (a) UEFI-time fix: D8 with corrected MAP GUID — clear DSDT page protection and patch
  *before* `ExitBootServices`, so Windows parses the corrected AML at boot; (b)
  boot-time kernel interception: a signed driver that hooks `acpi.sys` before namespace
  build (HVCI/Secure Boot ON — requires WHQL or a co-signed driver). Both remain
  untested. Full analysis in SESSION_LOG Session 52.
- **Live local-kernel-memory inspection — attempted, partially successful (Session 51,
  2026-06-08).** With local kernel debugging enabled and `kdARM64.exe -kl` attached,
  the live SPSS device object (`PDO 0xffffbd0ebd52cd50`, owned solely by `\Driver\ACPI`
  — confirming via `!devstack` that `qcsubsys.sys` never attached an FDO) was located
  and inspected directly in kernel memory:
  - `!devobj` showed `ExtensionFlags = DOE_START_PENDING` — the literal, live
    kernel-internal flag meaning "this device's start IRP is being withheld," observed
    directly rather than inferred from logs. This is the first first-hand, in-memory
    confirmation of the "device held pending" state the root-cause model predicts (see
    the updated §6 table row above).
  - `!error 0xc000003b` decoded the SPSS `Problem Status` to
    `STATUS_OBJECT_PATH_COMPONENT_NOT_A_DIRECTORY` — see the new open question below.
  - A targeted `s -a`/`s -u` string search for `QCOM0C87`/`QCSP`/`\_SB.QCSP` in a 2 MB
    window around `acpi.sys`'s code returned a clean negative; wider ranges (32 MB,
    2 GB) hung indefinitely and could not complete (see the brute-force-search item
    below). *Status: read-only live inspection succeeded and produced new evidence;
    locating the in-memory `_DEP`/dependency-tracking structure itself remains
    unresolved.* Full command list, raw logs, and analysis in SESSION_LOG Session 51
    and `diagnostic-captures/` (gitignored).
- **Chase the `0xc000003b` / `STATUS_OBJECT_PATH_COMPONENT_NOT_A_DIRECTORY` thread —
  new, surfaced in Session 51 (2026-06-08).** The SPSS devnode's `Problem Status`
  decodes to a far more specific NTSTATUS than the generic `CM_PROB_FAILED_ADD` label:
  "Object Path Component was not a directory object" — an Object Manager namespace
  traversal failure (some intermediate path component along a `\...` path was not a
  directory/container where one was expected). This was not previously decoded or
  discussed in 50 prior sessions. Worth investigating: *what* object-manager path is
  `acpi.sys`/`qcsubsys.sys` traversing when this fires — it could plausibly be, or lead
  to, the very namespace structure that records `_DEP`/dependency state, which neither
  the Session 50 ETW trace nor the Session 51 memory search could locate by other
  means. *Status: NTSTATUS decoded; the namespace path it refers to has not been
  identified.*
- ~~**Brute-force kernel-memory string search for `QCOM0C87`/`QCSP`/`\_SB.QCSP`**~~ —
  **attempted and closed as a confirmed tooling limitation (Session 51, 2026-06-08),**
  mirroring the Session 50 ETW conclusion in a different instrumentation layer. Every
  `s -a`/`s -u` search attempted over a wide address range (32 MB, then the originally
  planned full ~2 GB kernel range) hung indefinitely (6+ minutes, zero progress) and
  had to be force-killed; a `lm a <address>` lookup hung identically on network
  symbol-path resolution (`srv*`). Only a narrow, pre-targeted 2 MB window (chosen from
  addresses already known via `!drvobj`/`!devobj`, avoiding `lm` entirely) completed —
  in under a minute — and returned a clean negative. **This closes the brute-force
  variant**: a full-address-space string search is not practically achievable via
  local-KD `s` commands on this hardware/build. The avenue is *narrowed, not closed* —
  small, well-chosen windows remain viable *if* their addresses can be obtained without
  triggering the `lm`/symbol-resolution hang (e.g. candidates: `qcsubsys8380.sys` pool
  allocations, PnP-manager data structures, the ACPI namespace cache — all untried).
- **Cross-device DSDT comparison.** Compare DSDTs from other Snapdragon X 8380 /
  `CRD08380` machines or other Acer BIOS revisions. The decisive question: does a
  *working* board include `\_SB.SPSS` in QCSP's `_DEP`? If not, the Acer V1.09 table is
  almost certainly the defect. *Status: not attempted — no second board was available.*
- **Non-Windows ACPI dump.** Boot a Linux/WoA live environment far enough to run
  `acpidump` or read `/sys/firmware/acpi/tables`, to confirm the firmware DSDT content
  independent of Windows (and to see whether Linux tolerates the dependency
  differently). *Status: not attempted.*

### 11b — Candidate fix/workaround paths not yet attempted

These were surfaced as plausible but are **unverified for this board.** Each carries a
caveat this work could not resolve.

- **rEFInd bootloader ACPI loading.** `EFI_Injection_Tracking.md` lists rEFInd as a
  "next step if `AcpiInject.efi` fails," but it was never tried. rEFInd is a signed,
  mature EFI bootloader; the suggestion is that it performs protocol discovery and
  memory allocation more correctly than a hand-built PE binary. *Caveat: rEFInd's
  actual ability to inject/load an SSDT on ARM64 + Insyde H2O V1.09 is unverified here —
  do not assume it works until tested.* *Status: not attempted.*
- **UEFI Shell `acpiview` / table load.** Some Insyde firmwares are reported to expose
  `EFI_ACPI_TABLE_PROTOCOL` to the Shell environment but not to arbitrary PE apps.
  Trying the built-in Shell ACPI commands would test that. *Caveat: "Shell-only
  exposure" is a general report, not something confirmed on this unit.* *Status: not
  attempted.*
- **Alternate / vendor-specific ACPI protocol GUID.** Only the standard
  `EFI_ACPI_TABLE_PROTOCOL` GUID was used (and, in 5a–5g, the wrong GUID entirely —
  §8). A brute-force scan of all installed protocols at boot — including the older
  `{6DABB78A-FB9B-4DAB-8F83-E9DBE853AF76}` noted in `EFI_Injection_Tracking.md` — might
  reveal an Insyde-specific injection interface. *Status: not attempted.*
- **Windows kernel-side circumvention.** Rather than touch ACPI at all: an ACPI filter
  driver that publishes the PIL TZ interface (or fakes the dependency) before
  `qcsubsys.sys` requests it; a phantom `QCOM0C87` devnode via `IoReportDetectedDevice`
  to load `qcsp.sys` ahead of ACPI enumeration; or documented-but-unofficial registry
  overrides under `HKLM\SYSTEM\CurrentControlSet\Enum\ACPI` / `...\Services`. *Caveat
  this work treats as decisive: all kernel-driver paths require a signed or test-signed
  driver, and **HVCI is ON** on this device (Secure Boot was toggled off only for ACPI
  testing) — so these are materially harder than they appear and may be blocked
  outright.* *Status: not attempted.*
- **Offline boot-start staging of `qcsp.sys`.** An offline DISM apply was observed to
  produce the same failure state, but staging `qcsp.sys` as a boot-start driver
  (`Start = 0`) or otherwise manipulating driver-store load order — to publish PIL TZ
  before ACPI device enumeration — was not tried. *Caveat: it is unknown whether
  boot-start changes the PnP `_DEP` gate at all.* *Status: not attempted.*

### 11c — Out-of-band fix paths (the firmware routes)

- **Acer BIOS V1.10 or newer.** V1.09 is the latest available for NX.JP3ED.002 as of
  May 2026. A firmware update that removes `\_SB.SPSS` from QCSP's `_DEP` would resolve
  the deadlock with no further software work. Verification after a new BIOS:
  `ACPI\QCOM0C87` appears in PnP and PIL TZ `Linked` reads `1`. Risk: low (official
  firmware). *Status: not available as of this writing.*
- **Offline BIOS ROM modification (H2OFFT / UEFITool).** The byte change is known:
  inside the firmware image, replace the DSDT `_DEP[2]` `53 50 53 53` ("SPSS") with
  `47 4C 4E 4B` ("GLNK"). Requires extracting the image from SPI ROM (or via an
  Insyde update utility), unpacking and patching the DSDT, re-checksumming, repacking,
  and reflashing. Risk: **high — a failed reflash can brick the device**; a verified
  full firmware backup and an external recovery path are required first. *Status: not
  attempted.*

### 11d — Public disclosure (this repository)

No existing public write-up matching the QCOM0C87/SPSS `_DEP` deadlock on the 8380
CRD-class boards was found during this investigation. This repository is published as
that disclosure: the failure chain, the DSDT byte offsets, the fifteen-attempt UEFI
injection log, and the read-only ACPI memory finding (§9) are documented here so the
next person who hits this deadlock does not have to re-derive it. If it reaches someone
with a known workaround, a related-SKU fix, or Insyde firmware internals knowledge, all
the better. Risk: none beyond disclosure of research already in this repository.

---

## §12 — Reproducibility

The hardware, software, and tooling needed to replicate or extend this work.

**Hardware**
- Acer A14-11M, product code NX.JP3ED.002
- SoC: Qualcomm Snapdragon X 8380 (SUBSYS_CRD08380)
- USB-C port for installation media (USB-A produces a "missing drivers" error)

**Operating system**
- Windows 11 ARM64 26H1, build 26200

**Firmware**
- Insyde H2O, identifier `QCOMM_/SDM8380_/rev3`
- BIOS V1.09 (latest as of May 2026); confirm via `wmic bios get smbiosbiosversion`

**Install procedure**
- Per [caccialdo's gist](https://gist.github.com/caccialdo/3b0d0113489ecee456d94c1e9462d755),
  specifically t0ma5's writeup in the comment thread: FAT32-formatted USB,
  `install.wim` split into `.swm` parts via
  `Dism /Split-Image /ImageFile:X:\sources\install.wim /SWMFile:X:\sources\install.swm /FileSize:3800`,
  boot from a USB-C port.

**Driver sources**
- Acer OEM Qualcomm Base Driver 0.7700.1 for W11ARM64 (from Acer's support page
  for NX.JP3ED.002).
- WOA-Project Qualcomm Reference Drivers, folder `8380_CRD/200.0.57.0/`
  (https://github.com/WOA-Project/Qualcomm-Reference-Drivers).

**Toolchain for UEFI work**
- Python 3.8 or newer.
- `keystone-engine` (pip install) for building `AcpiInject.efi`.
- `iasl.exe` from acpica.org for recompiling SSDT ASL sources.

**Investigation protocol**
- Before any high-risk driver install or any UEFI experiment, capture a full
  system image backup using `wbadmin` to NTFS, or `DISM /capture-image` to
  exFAT.
- Build a SSDT test with `_HID = "QCOM1234"` and confirm `ACPI\QCOM1234`
  appears in Device Manager before attempting any real QCSP fix on the same
  injection method.
- Use Secure Boot OFF for ACPI-override testing; HVCI may remain ON.

---

## §13 — Artifact map

Every published file in this repository and what it contains.

| File | Contents |
|---|---|
| [`README.md`](../README.md) | Executive summary, current status, repository layout, vendor-response pointer |
| [`docs/FINDINGS.md`](FINDINGS.md) | This document — the synthesised research paper |
| [`docs/INDEX.md`](INDEX.md) | Navigation map: reading paths, topical map, attempt index, glossary, document map |
| [`docs/SESSION_LOG.md`](SESSION_LOG.md) | Chronological lab notebook covering 48 sessions of investigation |
| [`docs/ATTEMPTS.md`](ATTEMPTS.md) | Concise table of all override and injection attempts and their outcomes |
| [`docs/EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md) | Full chronological log of UEFI injection sub-attempts 5a–5o with byte-level detail |
| [`docs/AcpiInject_Findings.md`](AcpiInject_Findings.md) | Snapshot analysis of `build_efi.py`; identified the wrong-GUID bug |
| [`docs/Driver_Reference_Map.md`](Driver_Reference_Map.md) | Hardware ID to INF mapping for the Qualcomm driver package set |
| [`efi-injection/README.md`](../efi-injection/README.md) | Build and deploy instructions for `AcpiInject.efi`, plus attempt summary |
| [`efi-injection/build_efi.py`](../efi-injection/build_efi.py) | Python builder that assembles `AcpiInject.efi` (PE32+ AARCH64) |
| [`efi-injection/ssdt_qcsp.asl`](../efi-injection/ssdt_qcsp.asl) | ASL source for the stub SSDT (human-readable) |
| [`efi-injection/ssdt_qcsp.aml`](../efi-injection/ssdt_qcsp.aml) | Compiled SSDT binary (80 bytes) |
| `baselines/*.csv` | Four milestone PnP device snapshots taken at key investigation phases |

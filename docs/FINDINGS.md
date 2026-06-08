# Acer A14-11M — Qualcomm Driver Recovery on Windows 11 ARM64

> Research paper. For the chronological lab notebook, see [`SESSION_LOG.md`](SESSION_LOG.md).
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

The root cause is a circular dependency deadlock encoded in the system DSDT. The QCSP
device (`_HID = "QCOM0C87"`) carries an `_DEP` reference to `\_SB.SPSS`. SPSS
(`ACPI\QCOM0C8D`) cannot complete `AddDevice` because the PIL TZ interface
(`{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`) is not active. That interface is activated
by `qcsp.sys` — the driver for QCSP — but `qcsp.sys` never loads because QCSP is held
back by Windows ACPI's unsatisfied-`_DEP` gate. The deadlock is self-referential and
cannot be broken by driver installation alone.

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

With every in-band software path exhausted, only two out-of-band paths remain: a
future Acer BIOS update for the NX.JP3ED.002 SKU that removes SPSS from QCSP's `_DEP`,
or offline BIOS ROM modification with external tooling. Acer support offered Windows
Update and the purchase of physical recovery media; neither addresses the
firmware-level DSDT defect. The case remains open as of June 2026, with no Acer
follow-up since the single 22 May 2026 reply.

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

All remaining failures on the Acer A14-11M trace to a single circular dependency
embedded in the DSDT shipped with the Insyde H2O firmware. The dependency forms a
loop that Windows cannot resolve, blocking a critical security platform driver from
ever loading. Because that driver publishes an interface that several subsystem
drivers require, the loop propagates into at least 25 failing devices across audio,
compute, thermal, GPU, and Bluetooth stacks.

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
`STATUS_OBJECT_NAME_NOT_FOUND`). The root cause is that `qcsubsys.sys` attempts to
open the PIL TZ device interface during initialization, and that interface is not
present.

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

### 5l — `EFI_MEMORY_ATTRIBUTE_PROTOCOL` unprotect then patch (Sessions 40–41)

UEFI 2.10 introduced `EFI_MEMORY_ATTRIBUTE_PROTOCOL`
(GUID `{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}`), which exposes
`ClearMemoryAttributes()` to remove `EFI_MEMORY_RO` from specific pages. 5l called
`LocateProtocol` to obtain MAP, cleared the read-only attribute on the DSDT pages,
then issued the same byte patch as 5k. The DSDT remained unchanged. Either MAP is
absent on this Insyde H2O V1.09 firmware (`LocateProtocol` returned failure) or
`ClearMemoryAttributes()` succeeded against an upper page-table layer but a lower
firmware-managed layer continues to enforce write protection. Without a working
diagnostic channel, the two cases cannot be distinguished from inside the UEFI
application from 5l alone — this is what motivated Attempt 5m below.

### 5m — MAP canary write to localise the block (Sessions 46–47)

Attempt 5l could not distinguish whether `EFI_MEMORY_ATTRIBUTE_PROTOCOL` was
absent or present-but-ineffective. 5m added a canary to separate the two cases:
after calling `ClearMemoryAttributes()` on the DSDT pages, the application wrote
a known four-byte pattern to a benign DSDT field (`DSDT[0x20..0x23]`, the
CreatorRevision) and added a visible multi-second stall so the run could be
confirmed by eye. After reboot, the canary bytes read `00 00 00 05` —
**unchanged** from the pre-boot baseline — and the `_DEP` patch target at
`0x36C69` still read `SPSS`. The stall was observed, confirming the application
ran to that point. Conclusion: writes to firmware-managed ACPI pages are silently
dropped even after a MAP unprotect attempt. The direct DSDT-write path is
**permanently closed**.

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

3. **`EFI_MEMORY_ATTRIBUTE_PROTOCOL` (UEFI 2.10) is absent or non-functional for
   ACPI memory.** This is the standard UEFI API for changing memory page
   attributes. Without it, an EFI application cannot legitimately clear write
   protection on ACPI pages. Confirmed by Attempt 5l.

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

### The recovery media likely restores the working factory state

The Acer-supplied recovery media is the image the device shipped with. The device
worked at unboxing. The factory state evidently includes OEM driver provisioning
that is not reproducible from the public Acer driver packages — almost certainly
including either a pre-staged `qcsp.sys` activation path or a different ACPI
boot-time ordering that does not enter the deadlock. A factory restore from the
recovery media would, in all likelihood, restore that working state.

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

## §11 — Open questions

Every in-band software path has now been exhausted (§7, §8). The probes that
earlier drafts of this paper listed here as open — the MAP canary write (5m) and
`BootServices->InstallConfigurationTable()` (5n/5o) — have all been run and
failed; they are documented in §8. Two genuine paths remain, both out of band,
plus the public disclosure this repository constitutes.

### Acer BIOS V1.10 or newer

V1.09 is the latest available BIOS for NX.JP3ED.002 as of May 2026. A firmware
update that removes `\_SB.SPSS` from QCSP's `_DEP` list would resolve the
deadlock with no further software work. Check Acer's support page for this SKU
periodically. Verification after applying a new BIOS: `ACPI\QCOM0C87` should
appear in PnP and the PIL TZ `Linked` value should read `1`. Risk: low, assuming
official Acer firmware.

### BIOS ROM modification with offline tooling

If no firmware update is forthcoming and the in-band injection paths remain
blocked, the remaining option is offline modification of the firmware image.
The byte change is known: at the DSDT location inside the firmware ROM, replace
`53 50 53 53` with `47 4C 4E 4B`. This requires extracting the firmware image
from the SPI ROM with a programmer (or with an Insyde-specific update utility
such as `H2OFFT`), unpacking the DSDT, patching it, re-checksumming, repacking,
and reflashing. Risk: high. A failed reflash can brick the device. A verified
working backup of the original firmware is required before any attempt.

### Public disclosure (this repository)

No existing public write-up matching the QCOM0C87/SPSS `_DEP` deadlock on the
8380 CRD-class boards was found during this investigation. This repository is
published as that disclosure: the full failure chain — the DSDT byte offsets, the
fifteen-attempt UEFI injection log, and the read-only ACPI memory finding from §9
— is documented here so that the next person who hits this deadlock after a clean
reinstall does not have to re-derive it from scratch. If it reaches someone with
a known workaround, a related-SKU fix, or Insyde firmware internals knowledge,
all the better; but the primary goal is to make the dead ends and the one viable
remaining path (a corrected BIOS) findable. Risk: none beyond public disclosure
of research already contained in this repository.

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

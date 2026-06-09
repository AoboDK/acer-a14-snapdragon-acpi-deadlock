# Acer A14-11M (NX.JP3ED.002) — Windows 11 ARM64 Driver Recovery

**Status: Research case study — partial recovery documented, full fix not yet achieved.**
This repo documents an investigation into recovering Qualcomm platform drivers on a
Snapdragon X 8380 laptop after a clean OS reinstall (forced by the built-in Windows
"Reset this PC" leaving the device in an unbootable Acer-logo loop). All standard ACPI
override methods and a series of custom UEFI injection approaches have been exhausted.
The findings — including exact failure modes, firmware behavior, and a precise root
cause — are published here as a reference for others hitting the same deadlock.

---

## Hardware

| | |
|---|---|
| Model | Acer Swift 14 AI (A14-11M) — product code NX.JP3ED.002 |
| SoC | Qualcomm Snapdragon X 8380 (CRD/SUBSYS_CRD08380) |
| OS | Windows 11 ARM64 (build 26200) |
| UEFI | Insyde H2O, QCOMM_/SDM8380_ rev3, V1.09 |
| Secure Boot | OFF (disabled for driver testing) |
| HVCI | ON |

---

## The problem

**How the machine got here:** the factory OS was wiped with the built-in Windows
**Settings → System → Recovery → Reset this PC**. After the reset, the device would
not boot — it hung in a loop at the Acer logo and never reached Windows. With the
in-box recovery path dead, the only way back to a working OS was a clean reinstall
from a fresh, official Microsoft Windows 11 ARM64 ISO on USB. Every observation in
this repo is from that clean reinstall.

After that clean Windows 11 ARM64 (26H1) install on this SKU, roughly 20+ Qualcomm
platform devices fail to start. The install procedure used is the FAT32-USB + split
`install.wim` method documented by t0ma5 in caccialdo's gist
([gist.github.com/caccialdo/3b0d0113489ecee456d94c1e9462d755](https://gist.github.com/caccialdo/3b0d0113489ecee456d94c1e9462d755)),
booted from a USB-C port.

Acer's bundled `Setup_Driver.cmd` cannot be used to recover from this state: it
bulk-installs every driver in one shot and triggers a **BSOD** ("SOC critical device
removed") mid-install on an already-broken system. Recovery from that BSOD requires
a restore point or a full re-image.

The safe partial-recovery path documented here is to install drivers one INF at a
time, in the right order, using `pnputil /add-driver <path> /install`. This restores
roughly 60% of the Qualcomm stack but is blocked from full recovery by a circular
ACPI `_DEP` deadlock at the firmware level (see root-cause section below).

> **Footnote:** An early one-off test used offline DISM apply from another PC; the
> resulting driver state was the same. That test does not reflect the install state
> under which the investigation in this paper was conducted.

**Full investigation, findings, and open questions:** see [`docs/FINDINGS.md`](docs/FINDINGS.md).
**Navigation map across all docs:** see [`docs/INDEX.md`](docs/INDEX.md).

---

## What works after safe single-INF install

| Component | Status |
|---|---|
| WiFi, Display, Keyboard, Trackpad | Working |
| USB, Card Reader, Camera, NPU | Working |
| PMIC Apps, PMIC GLink, TFTP, SCM | Running |
| GLINK, IPC Router, IPCC, Syscache, SMMU | Running |
| PIL (`qcPILC`), PIL Filter (`qcPILFC`) | Running |
| `qcsubsys` service | Running |

## What is still broken

| Component | Problem |
|---|---|
| ADSP / CDSP / SPSS | `CM_PROB_FAILED_ADD` |
| QCPEP thermal/policy cluster (17 devices) | `STATUS_NO_SUCH_DEVICE` |
| Bluetooth | Transport OK, radio device unresolved |
| Audio | Blocked by ADSP failure |
| Adreno GPU | Failing |
| Battery reporting | Blocked |

---

## Root cause: circular ACPI `_DEP` deadlock

The **major Qualcomm subsystem cascade** — ADSP/CDSP/SPSS, and through them audio,
Bluetooth radio, GPU, and the thermal-policy cluster — traces to one circular
dependency in the ACPI tables shipped with this firmware:

```
QCSP device (ACPI\QCOM0C87) has _DEP on \_SB.SPSS
  -> SPSS (ACPI\QCOM0C8D) fails AddDevice because PIL TZ interface is inactive
  -> PIL TZ interface is inactive because qcsp.sys never loaded
  -> qcsp.sys never loaded because QCSP was never presented to PnP
  -> QCSP not presented because Windows holds back devices with unsatisfied _DEP
  -> deadlock
```

> **Proof status.** The observed states (QCSP absent, SPSS failing, PIL TZ blank) and
> the DSDT `_DEP` are directly established. The step "Windows holds QCSP back
> *specifically because* `\_SB.SPSS` is unresolved" is **strongly indicated but
> inferred** — it has not been captured with an ETW/Kernel-PnP or WinDbg trace. Some
> *secondary* device failures (ADC, UART, HPS, EVA, ISP camera, HID Button) are listed
> as "needs investigation" and are **not yet proven** to be downstream of this
> deadlock. See [`docs/FINDINGS.md` §6 Limitations](docs/FINDINGS.md) and
> [§11](docs/FINDINGS.md).

Breaking the deadlock requires injecting a stub ACPI SSDT table that creates a
dependency-free version of the QCSP device (HID `QCOM0C87`, no `_DEP`) so that
`qcsp.sys` can load and activate the PIL TZ interface.

---

## Why standard ACPI override methods don't work on this platform

| Method | Why it fails |
|---|---|
| `HKLM\...\acpitables` registry + `ACPIOVERRIDETEST` BCD flag | x86/BIOS-only; ignored on ARM64 UEFI |
| SSDT files in ESP (`S:\EFI\ACPI\`, etc.) | Insyde firmware on this board does not load them |
| DSDT binary patch via `acpitables` | Same registry mechanism — dead on ARM64 |
| GRUB2 `acpi` module + chainloader | GRUB modifies XSDT in RAM but does not update the EFI ConfigurationTable RSDP pointer; Windows ARM64 ignores it |
| `EFI_ACPI_TABLE_PROTOCOL->InstallAcpiTable()` | Not usable from the tested boot app; absent-vs-rejected unresolved (builds 5a–5g used the wrong protocol GUID — see §8) |
| Direct XSDT modification (write `RSDP->XsdtAddress`) | RSDP is in firmware read-only memory; write silently dropped |
| DSDT in-place byte patch | DSDT pages also read-only; write silently dropped |
| `EFI_MEMORY_ATTRIBUTE_PROTOCOL->ClearMemoryAttributes()` + patch | **5l/5m INVALID — wrong GUID** (`{6A7A5CFF...}` = `EFI_COMPONENT_NAME2_PROTOCOL`). MAP never actually invoked. Retest pending (D8 with correct GUID `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}`). |

Not all software-only paths have been cleanly tested — see the 5l/5m audit note.
See [`docs/ATTEMPTS.md`](docs/ATTEMPTS.md) for the full table and remaining options.

---

## UEFI injection attempts: `AcpiInject.efi`

See [`efi-injection/`](efi-injection/) for the Python builder and SSDT source.
See [`docs/EFI_Injection_Tracking.md`](docs/EFI_Injection_Tracking.md) for the
full attempt log (5a through 5o).

**Summary of what was tried and failed:**

| Attempt | Approach | Result |
|---|---|---|
| 5a–5c | GRUB chainloader → AcpiInject.efi | Shim security hook blocked; PE loader rejected (wrong headers) |
| 5d | Fixed PE headers (NumDirEntries=16, DllChars=0x0100) | Binary ran — but SSDT never appeared |
| 5e–5g | Debug logging (file, NVRAM variable) | All I/O blocked: SFS write-protected, NVRAM vars blocked (error 1314) |
| 5h | `EFI_ACPI_TABLE_PROTOCOL->InstallAcpiTable()` | SSDT never in `HKLM\HARDWARE\ACPI\SSDT`; absent-vs-rejected not cleanly distinguishable (5a–5g used the wrong GUID) |
| 5i–5j | Direct XSDT append in EfiACPIMemoryNVS | RSDP->XsdtAddress write silently dropped (RSDP is read-only firmware memory) |
| 5k | DSDT in-place byte patch | DSDT pages also write-protected; write silently dropped |
| 5l | `EFI_MEMORY_ATTRIBUTE_PROTOCOL->ClearMemoryAttributes()` before DSDT patch | **INVALID — wrong GUID** (`{6A7A5CFF...}` = Component Name 2, not MAP). MAP never invoked; result does not establish MAP absent. Correct GUID `{F4560CF6...}`; retest pending (D8). |
| 5m | MAP unprotect + canary write to `DSDT[0x20]` | **INVALID — same wrong GUID as 5l.** "Permanently closed" conclusion withdrawn; retest required. |
| 5n | `BootServices->InstallConfigurationTable()` with new RSDP/XSDT/SSDT chain in NVS | Only "Compal" SSDT key after boot — replacement chain not parsed by Windows |
| 5o | 5n + on-screen `ICT=`/`CT=` diagnostics | Tested; failed — SSDT not injected, deadlock not broken. `InstallConfigurationTable()` path closed |

**Current status (after Attempt 5o, June 2026):** All software-only injection
paths are exhausted. The RSDP, XSDT, and DSDT all reside in firmware-managed
read-only memory pages on this Qualcomm/Insyde platform. `EFI_ACPI_TABLE_PROTOCOL`
could not be used from the tested boot app — and whether it is genuinely absent or
merely rejected the call was never cleanly determined, because builds 5a–5g queried
the wrong protocol GUID (see [`docs/FINDINGS.md` §8](docs/FINDINGS.md)). UEFI runtime
variable services are fully blocked from Windows (error 1314 for all variables
including `BootOrder`). Even the firmware's own `InstallConfigurationTable()` service
does not cause Windows to parse a replacement ACPI chain. No **in-band ACPI-injection**
mechanism from a UEFI boot app remains; out-of-band and OS-side paths are catalogued
as untried in [`docs/FINDINGS.md` §11](docs/FINDINGS.md).

**Remaining paths.** What is exhausted is *in-band ACPI injection from a UEFI boot
app* — not every avenue. The two firmware fix routes are out of band:
1. **BIOS update** — check Acer for V1.10+ for NX.JP3ED.002 that removes SPSS from
   QCSP's `_DEP`. Zero further software work if shipped. V1.09 is latest as of May 2026.
2. **BIOS ROM modification** via UEFITool / Insyde tools — patch the DSDT `_DEP`
   inside the firmware image and reflash. High risk; requires a verified backup.

Beyond those, several **untried** paths — validation (factory-image diff, ETW/WinDbg
proof, cross-device DSDT compare, live-kernel DSDT patch) and candidate fixes (rEFInd,
UEFI Shell, alternate ACPI protocol GUID, kernel-side filter/phantom-devnode) — are
catalogued honestly, with their caveats, in [`docs/FINDINGS.md` §11](docs/FINDINGS.md).
None have been attempted; none are claimed to work.

This repository is itself the public disclosure of the full failure chain, so the
next person hitting this deadlock does not have to re-derive it.

---

## Driver install log (safe single-INF method)

Full session history including exact commands, outputs, and outcomes is in
[`docs/SESSION_LOG.md`](docs/SESSION_LOG.md).

### Driver sources used

| Source | URL / location |
|---|---|
| Acer OEM package | Downloaded from Acer support for NX.JP3ED.002 |
| WOA-Project reference drivers | https://github.com/WOA-Project/Qualcomm-Reference-Drivers (`8380_CRD/200.0.57.0/`) |
| `qcsp8380` (WOA, v1.0.4478.2200) | `oem103.inf` — staged, not yet active |

All drivers installed via:
```powershell
pnputil /add-driver "C:\path\to\driver.inf" /install
```

Never use `/subdirs` or bulk install scripts on an existing Windows install.

### Safe install order for platform drivers

1. `qcpep` (thermal/policy) — stage-only first, reboot, verify no BSOD
2. `qcsmmu` (IOMMU) — stage-only, reboot
3. `qcscm` (secure channel manager) — stage-only, reboot
4. `qcPILC` / `qcPILFC` (PIL) — install, reboot
5. `qcsubsys` (subsystem manager) — install, reboot
6. PMIC drivers (`qcpmicapps`, `qcpmicglink`) — install, reboot
7. `qcGLINK`, `qcIPCR`, `qcIPCC`, `qcqsap`, `qcTFTP`, `qcsyscache` — install, reboot
8. **ACPI deadlock must be broken before proceeding further**

---

## Replication prerequisites

- Windows 11 ARM64 installed on the target device
- PowerShell 7 (`pwsh`) — comes with Windows 11 but confirm version
- `pnputil` — built into Windows
- Acer driver package for NX.JP3ED.002 (download from Acer support)
- Python 3.x + `keystone-engine` (`pip install keystone-engine`) — for building AcpiInject.efi
- `iasl.exe` from https://www.acpica.org/downloads — for recompiling the SSDT if needed
- A FAT32 USB drive (any size) for the EFI injector

---

## Repository layout

```
README.md                          <- This file (executive summary + current status)
.gitignore
docs/
  FINDINGS.md                      <- Synthesised research findings (start here for the science)
  INDEX.md                         <- Navigation map: topics, attempts, identifiers, glossary
  SESSION_LOG.md                   <- Full chronological lab notebook (48 sessions)
  ATTEMPTS.md                      <- Concise attempt summary table
  EFI_Injection_Tracking.md        <- Full UEFI injection attempt log (5a–5o)
  AcpiInject_Findings.md           <- PE binary analysis (the GUID bug)
  Driver_Reference_Map.md          <- Hardware ID to INF mapping table
efi-injection/
  build_efi.py                     <- Python script that builds AcpiInject.efi
  ssdt_qcsp.asl                    <- SSDT ASL source (human-readable)
  ssdt_qcsp.aml                    <- Compiled SSDT binary (80 bytes)
  ssdt_test.asl                    <- Canary SSDT (HID QCOM1234) used to verify injection paths
  README.md                        <- Build instructions + attempt summary
scripts/
  inject_ssdt.ps1                  <- Attempt 1: SSDT via acpitables registry
  inject_dsdt.ps1                  <- Attempt 3: patched DSDT via acpitables registry
  update_acpitables.ps1            <- Canary test script for Attempts 1 and 3
  esp_inject.bat                   <- Attempt 2: SSDT placed in ESP candidate paths
  esp_test.bat                     <- Attempt 2 canary pre-test
  README.md                        <- Script-to-attempt mapping table
baselines/
  A14_*.csv                        <- Key PnP device snapshots at milestone phases
```

---

## Vendor support response

A detailed technical writeup of the bug was escalated to Acer support. The single
reply (22 May 2026) offered only Windows Update and the purchase of physical recovery
media as remediation paths, with no engagement on the technical content and no
escalation to a firmware or BIOS team. As of **8 June 2026** there has been no further
response — over two weeks of silence after that one reply. See
[`docs/FINDINGS.md` §10](docs/FINDINGS.md) for the full account, the verbatim reply,
and the analysis of why each offered remediation does or does not address the
documented bug.

---

## Contributing / related hardware

If you have a Snapdragon X (8cx Gen 4, X Elite, X Plus, or 8380) device with
the same or similar symptoms after a clean Windows reinstall, please open an
issue. This work may apply to other Qualcomm CRD-class boards beyond the
NX.JP3ED.002.

Relevant upstream projects:
- [WOA-Project/Qualcomm-Reference-Drivers](https://github.com/WOA-Project/Qualcomm-Reference-Drivers)
- [WOA-Project/Mu-Silicium](https://github.com/WOA-Project/Mu-Silicium)

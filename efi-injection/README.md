# AcpiInject.efi — UEFI ACPI injector for Snapdragon X / Insyde H2O

> **Status: Research artifact — all in-band injection approaches (5a–5o) exhausted.**
> See the attempt log below and [`docs/EFI_Injection_Tracking.md`](../docs/EFI_Injection_Tracking.md)
> for full details. For the narrative synthesis, see [`docs/FINDINGS.md §8–9`](../docs/FINDINGS.md).
> For navigation across all docs, see [`docs/INDEX.md`](../docs/INDEX.md).

A hand-crafted PE32+ AARCH64 EFI application that attempts to break the QCSP/SPSS
circular ACPI `_DEP` deadlock on the Acer A14-11M (Snapdragon X 8380) by modifying
the ACPI table chain before Windows boots.

**The goal:** patch `QCSP._DEP[2]` from `\_SB.SPSS` → `\_SB.GLNK` in the live DSDT
so `qcsp.sys` loads, the PIL TZ interface activates, and the ADSP/CDSP/GPU/BT cascade
starts.

---

## Files

| File | Description |
|---|---|
| `build_efi.py` | Python 3 builder — assembles ARM64 UEFI app with keystone-engine, emits PE32+ |
| `ssdt_qcsp.asl` | SSDT stub in ACPI ASL (human-readable) — original SSDT injection approach |
| `ssdt_qcsp.aml` | Compiled SSDT binary (80 bytes, iasl output) |

`AcpiInject.efi` is NOT checked in — build it from the script.

---

## Final build (Attempt 5o)

The script evolved across fifteen sub-attempts (5a–5o); see the full log below. The
final build is the Attempt 5o diagnostic, which uses the firmware's own
`InstallConfigurationTable()` service rather than writing protected memory:

1. Walk `SystemTable->ConfigurationTable` → locate the ACPI 2.0 GUID entry → read RSDP (read-only)
2. `AllocatePages(EfiACPIMemoryNVS, 4 pages)` → build a fresh RSDP → XSDT → SSDT chain in writable NVS
   (new XSDT with the 80-byte QCSP stub appended; all checksums recomputed)
3. `InstallConfigurationTable(&ACPI_20_GUID, new_rsdp)` to repoint the ACPI 2.0 entry
4. Print `[AI] ICT=OK/ERR` and `[AI] CT=OURS/OLD/NONE`, then an 8-second `Stall` so the output is readable
5. Chainload `\EFI\Microsoft\Boot\bootmgfw.efi` → Windows boots

**Result: FAILED.** After boot, `HKLM\HARDWARE\ACPI\SSDT` shows only the firmware's
own "Compal" key — no `QCOMM_` — and `ACPI\QCOM0C87` is still absent from PnP. The
firmware's `InstallConfigurationTable()` service does not result in Windows parsing
the replacement ACPI chain. Combined with the earlier DSDT/RSDP write failures (5i–5m,
all silently dropped on firmware-managed read-only pages) and the absent
`EFI_ACPI_TABLE_PROTOCOL`, every in-band software path is now closed. No logging
mechanism is available either (file I/O and NVRAM variables are both blocked from the
UEFI app context), which is why 5o relies on on-screen `ConOut` diagnostics.

---

## Prerequisites

```
pip install keystone-engine
```

Python 3.8+ required. No other dependencies.

To modify and recompile `ssdt_qcsp.asl`, you need `iasl.exe` from
https://www.acpica.org/downloads.

---

## Build

```powershell
python build_efi.py
```

Output: `C:\Drivers\AcpiInject.efi` (path hard-coded in the script; edit if needed).

Toggle flag at the top of `build_efi.py`:

| Flag | Default | Effect |
|---|---|---|
| `SKIP_ACPI` | `False` | `True` = skip Phase 1, test only the Windows chainload |

---

## Deploy to USB

```powershell
# FAT32 USB drive assumed at D:
Copy-Item "C:\Drivers\AcpiInject.efi" "D:\EFI\BOOT\BOOTAA64.EFI" -Force
```

Boot from USB via F12. No GRUB or Shim needed — the app runs directly as the
primary EFI boot application. After injection attempt, it chainloads Windows from
the internal NVMe.

---

## What does NOT work on this platform (confirmed dead)

| Approach | Reason |
|---|---|
| `HKLM\...\acpitables` registry + `ACPIOVERRIDETEST` BCD | x86/BIOS only; ignored on ARM64 UEFI |
| SSDT files in ESP (`S:\EFI\ACPI\`, etc.) | Insyde firmware does not load them |
| GRUB2 `acpi` module + chainloader | Modifies XSDT in RAM but does not update EFI ConfigurationTable RSDP pointer; Windows ARM64 ignores it |
| `EFI_ACPI_TABLE_PROTOCOL->InstallAcpiTable()` | Protocol absent or rejected on Insyde H2O V1.09 |
| Direct XSDT append in EfiACPIMemoryNVS | RSDP->XsdtAddress is in read-only firmware memory; write silently dropped |
| DSDT in-place patch without unprotect | DSDT pages also read-only; write silently dropped |
| `EFI_MEMORY_ATTRIBUTE_PROTOCOL->ClearMemoryAttributes()` + DSDT patch | MAP protocol absent or also blocked; DSDT unchanged (canary confirmed, 5m) |
| `BootServices->InstallConfigurationTable()` with new RSDP/XSDT/SSDT chain | Replacement not parsed by Windows; only "Compal" SSDT key after boot (5n/5o) |
| UEFI NVRAM variable logging (`SetVariable`) | Runtime variable services fully blocked (error 1314 for all variables) |
| File logging from UEFI app | All SFS volumes (USB and NVMe ESP) refuse file creation from UEFI app context |

---

## Attempt log summary

| ID | Approach | Sessions | Result |
|---|---|---|---|
| 5a | GRUB chainloader → AcpiInject.efi | 30 | Shim security hook blocked `LoadImage` |
| 5b | AcpiInject.efi directly as BOOTAA64.EFI | 31 | PE loader rejected — missing `MEM_WRITE` flag |
| 5c | Debug build with ConOut output | 32–33 | No output — PE loader rejected (wrong NumDirEntries/DllChars) |
| 5d | Fixed PE headers + log-before-ConOut | 33–34 | Binary ran; log file not created (wrong EFI_FILE_PROTOCOL offsets) |
| 5e | EFI_FILE_PROTOCOL Write/Flush offset fix | 34–35 | Log still absent |
| 5f | Brute-force SFS scan for log setup | 35–36 | Log still absent — USB SFS handle not returned by LocateHandleBuffer |
| 5g | Remove marker check, create log on first writable SFS | 36–37 | Log still absent — NVMe SFS refuses CREATE |
| 5h | Replace file logging with UEFI NVRAM variable | 37–38 | Error 1314 — all UEFI variables blocked |
| 5i | Direct XSDT append (RSDP->XsdtAddress patch) | 38–39 | SSDT not parsed — RSDP write silently dropped |
| 5j | SSDT pointer in EfiACPIMemoryNVS | 39–40 | SSDT not parsed — same RSDP write failure |
| 5k | DSDT in-place `_DEP` patch (no unprotect) | 40 | DSDT unchanged — DSDT pages also read-only |
| 5l | MAP protocol unprotect + DSDT patch | 40–41 | DSDT unchanged — MAP absent or blocked |
| 5m | MAP unprotect + canary write to `DSDT[0x20]` + stall | 46–47 | Canary unchanged after boot — DSDT write path permanently closed |
| 5n | `BootServices->InstallConfigurationTable()` (new chain in NVS) | 47–48 | Only "Compal" SSDT key — replacement not parsed by Windows |
| 5o | 5n + on-screen `ICT=`/`CT=` diagnostics + 8s stall | 48 | Tested; failed — SSDT not injected, deadlock not broken |

Full details with exact binary sizes, hashes, and post-boot diagnostics:
[`docs/EFI_Injection_Tracking.md`](../docs/EFI_Injection_Tracking.md)

---

## Remaining paths (out of band)

Every in-band software path (5a–5o) has been attempted and has failed. Only two
out-of-band paths remain:

1. **Acer BIOS V1.10+** — a firmware update that removes SPSS from QCSP's `_DEP`
   resolves the deadlock with zero further software work. V1.09 is latest as of May 2026.
2. **Offline BIOS ROM modification** — patch the DSDT `_DEP` (SPSS→GLNK at `0x36C69`)
   inside the firmware image with UEFITool / Insyde tooling and reflash. High brick
   risk; requires a verified firmware backup.

This repository is published as the public disclosure of the full failure chain.

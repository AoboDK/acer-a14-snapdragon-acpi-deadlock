# ACPI Injection Attempts — Summary Table

> Concise attempt-by-attempt summary. For the narrative synthesis, see
> [`FINDINGS.md §8`](FINDINGS.md). For navigation, see [`INDEX.md`](INDEX.md).

All attempts to break the QCSP/SPSS circular `_DEP` deadlock on the
Acer A14-11M (Snapdragon X 8380, Insyde H2O V1.09, HVCI ON, Secure Boot OFF).

**Goal:** Make `ACPI\QCOM0C87` appear in PnP so `qcsp.sys` loads, activating
the PIL TZ interface (`{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`, `Linked=1`),
which unblocks SPSS → ADSP/CDSP/BT/audio/GPU.

**Diagnostic oracle:** `HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003:00000000`
at offset `0x36C69` — `53 50 53 53` ("SPSS") = unchanged, `47 4C 4E 4B` ("GLNK") = patched.

---

## Pre-UEFI approaches (Attempts 1–4)

| ID | Method | Sessions | Result |
|---|---|---|---|
| 1 | `acpitables` registry + `ACPIOVERRIDETEST` BCD | 16–17 | DEAD — registry mechanism is x86/BIOS only; ARM64 ignores it |
| 2 | SSDT files in ESP (`S:\EFI\ACPI\`, etc.) | 17 | DEAD — Insyde firmware on this board does not load ESP SSDTs |
| 3 | Binary-patched DSDT loaded via `acpitables` | 22–23 | DEAD — same registry mechanism; live DSDT confirmed unchanged |
| 4 | GRUB2 `acpi` module + chainloader | 23–25 | DEAD — GRUB modifies XSDT in RAM but does not update EFI ConfigurationTable RSDP; Windows ARM64 ignores it |

---

## UEFI application approaches (Attempt 5)

All sub-attempts use a custom Python-built PE32+ AARCH64 EFI app
deployed as `D:\EFI\BOOT\BOOTAA64.EFI` on a FAT32 USB drive.

| ID | Key change | Sessions | Result |
|---|---|---|---|
| 5a | GRUB chainloader → AcpiInject.efi | 30 | FAILED — Ubuntu Shim's `EFI_SECURITY_ARCH_PROTOCOL` hook blocked `LoadImage` for unsigned binary |
| 5b | App directly as BOOTAA64.EFI (bypass Shim) | 31 | FAILED — ARM64 permission fault: section had `MEM_EXECUTE\|MEM_READ` but not `MEM_WRITE`; global variables written → fault |
| 5c | Added `MEM_WRITE` flag + ConOut debug output | 32–33 | FAILED — no output at all; PE loader rejected binary (NumDirEntries=0, DllChars=0x0000) |
| 5d | Fixed PE: NumDirEntries=16, DllChars=0x0100, `.reloc` section | 33–34 | PARTIAL — binary ran; log file not created (wrong `EFI_FILE_PROTOCOL` offsets: Delete used instead of Write) |
| 5e | Fixed file protocol offsets (Write=+40, Flush=+80) | 34–35 | FAILED — log still absent |
| 5f | Brute-force SFS scan; removed marker check | 35–36 | FAILED — USB SFS handle not returned by `LocateHandleBuffer(ByProtocol, SFS_GUID)` on this firmware |
| 5g | Try first NVMe SFS handle for log without marker | 36–37 | FAILED — NVMe ESP SFS refuses `Open(CREATE)` from UEFI app context |
| 5h | UEFI NVRAM variable logging (`SetVariable`) instead of file | 37–38 | FAILED — `GetFirmwareEnvironmentVariableW` returns error 1314 for ALL variables (incl. standard `BootOrder`); UEFI runtime variable services fully blocked |
| 5i | Direct XSDT modification: allocate NVS page, append SSDT pointer, write `RSDP->XsdtAddress` | 38–39 | FAILED — RSDP write silently dropped; RSDP is in firmware-managed read-only memory; SSDT not parsed by Windows |
| 5j | Same as 5i but SSDT data also in NVS (not EfiLoaderCode) | 39–40 | FAILED — same RSDP write failure; SSDT not parsed |
| 5k | DSDT in-place `_DEP` byte patch (SPSS→GLNK at offset 0x36C69) without unprotect | 40 | FAILED — DSDT pages also write-protected; write silently dropped; `DSDT[0x36C69]` = `53 50 53 53` ("SPSS") |
| 5l | `EFI_MEMORY_ATTRIBUTE_PROTOCOL->ClearMemoryAttributes()` to unprotect DSDT, then patch | 40–41 | FAILED — DSDT unchanged; MAP protocol (UEFI 2.10 spec, GUID `{6A7A5CFF...}`) absent on Insyde H2O V1.09 or also blocked for ACPI memory |
| 5m | MAP unprotect + canary write to `DSDT[0x20]` (CreatorRevision) + visible stall | 46–47 | FAILED — stall observed (app ran), canary unchanged after boot (`00 00 00 05`). Writes silently dropped even after MAP unprotect. DSDT write path **permanently closed** |
| 5n | `BootServices->InstallConfigurationTable()` (offset +0x0C0) — build new RSDP/XSDT/SSDT chain in `EfiACPIMemoryNVS`, repoint ACPI 2.0 GUID entry | 47–48 | FAILED — only "Compal" SSDT key after boot, no `QCOMM_`. Replacement chain not parsed by Windows. (Stall routine had wrong offset 232/`ExitBootServices` vs 248/`Stall`; did not affect the ICT call at offset 192) |
| 5o | 5n + ConOut `ICT=OK/ERR` and `CT=OURS/OLD/NONE` diagnostics + corrected 8s stall | 48 | FAILED — tested; SSDT not injected (only "Compal"), `ACPI\QCOM0C87` absent, deadlock not broken. `InstallConfigurationTable()` path closed |

---

## Root cause summary

The entire ACPI table chain (RSDP, XSDT, FADT, DSDT) lives in firmware-managed
read-only EFI memory pages on this Qualcomm/Insyde platform. No EFI application
can write to them:

- `EFI_ACPI_TABLE_PROTOCOL` is absent or returns failure
- Direct pointer writes (`RSDP->XsdtAddress`) are silently dropped
- Direct byte writes to DSDT are silently dropped (no ARM64 fault — just ignored)
- `EFI_MEMORY_ATTRIBUTE_PROTOCOL` (the API to change page attributes) is absent or also blocked
- `BootServices->InstallConfigurationTable()` (the firmware's own service to swap the ACPI chain) does not cause Windows to parse the replacement — confirmed by 5n/5o

Additionally, no diagnostic mechanism works:
- File I/O from UEFI app: blocked (USB SFS not enumerated; NVMe ESP SFS refuses CREATE)
- UEFI NVRAM variables: blocked for all variables (error 1314)

Every in-band software path (5a–5o) is now exhausted.

---

## Remaining paths (out of band)

| ID | Approach | Risk | Notes |
|---|---|---|---|
| — | Acer BIOS V1.10+ | None (official firmware) | Resolves the bug with zero further software work if Acer ships a BIOS removing SPSS from QCSP's `_DEP`. Check Acer support page for NX.JP3ED.002; V1.09 is latest as of May 2026 |
| — | BIOS ROM mod (UEFITool / Insyde tools) | High (brick risk) | Edit the DSDT `_DEP` (SPSS→GLNK at offset 0x36C69) inside the firmware image and reflash; requires a verified firmware backup |
| — | Public disclosure (this repository) | None | The full failure chain is published here so others hitting this deadlock need not re-derive it |

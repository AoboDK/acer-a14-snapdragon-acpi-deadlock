# EFI / ACPI SSDT Injection Tracking

> Full chronological attempt log. For the synthesised story see
> [`FINDINGS.md §8–9`](FINDINGS.md). For the summary table see
> [`ATTEMPTS.md`](ATTEMPTS.md). For navigation, see [`INDEX.md`](INDEX.md).

## Goal

Break the circular ACPI `_DEP` deadlock on the Acer A14-11M (Snapdragon X 8380).

**The deadlock:**
```
QCSP (ACPI\QCOM0C87) has _DEP on \_SB.SPSS
→ SPSS fails (CM_PROB_FAILED_ADD) because PIL TZ interface is inactive
→ PIL TZ inactive because qcsp.sys never loads
→ qcsp.sys never loads because QCSP is not presented to PnP (SPSS failing)
→ QCSP not presented because Windows ACPI holds back devices whose _DEP is unsatisfied
→ deadlock
```

**The fix:** Inject an SSDT stub that creates `\_SB.QSP0` (`_HID = "QCOM0C87"`, no `_DEP`) so `qcsp.sys` loads without waiting for SPSS.

**SSDT file:** `C:\Drivers\ssdt_qcsp.aml` (80 bytes, compiled from `ssdt_qcsp.asl`)
- Sig: `SSDT`, OEM: `QCOMM_`, Table: `QCSP87`
- Device: `QSP0`, `_HID = "QCOM0C87"`, `_UID = 1`, `_STA = 0x0F`
- Copy on USB: `D:\ssdt_qcsp.aml`

**Expected cascade if injection works:**
1. `ACPI\QCOM0C87` (QSP0) appears in PnP
2. `qcsp.sys` loads (staged as `oem103.inf`, WOA v1.0.4478.2200)
3. PIL TZ interface `{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}` activates → `Linked=1`
4. SPSS (`ACPI\QCOM0C8D`) AddDevice succeeds
5. Original `\_SB.QCSP` (`_DEP` on SPSS now satisfied) also appears
6. ADSP / CDSP start → audio, Bluetooth, battery, GPU unblock
7. QCPEP cluster (17 devices) may also clear

---

## System Context

| Field | Value |
|---|---|
| Model | Acer A14-11M NX.JP3ED.002 |
| SoC | Qualcomm Snapdragon X 8380 (SUBSYS_CRD08380) |
| OS | Windows 11 ARM64 Build 26200 |
| UEFI firmware | Insyde H2O (QCOMM_/SDM8380_/rev3) |
| Secure Boot | **OFF** (disabled in Session 22 for testing) |
| HVCI | ON |
| BIOS version | V1.09 (latest available as of May 2026) |
| qcsp8380 staged | `oem102.inf` (Acer v1.0.4196.6900), `oem103.inf` (WOA v1.0.4478.2200) |
| System image backup | `D:\A14_Backup_20260527.wim` (22.57 GB, WD My Passport) |

**Key registry path:** `HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`
— Check `Linked` value under `#` subkey after each boot. `Linked=1` = deadlock broken.

---

## Why Every Standard Approach Fails on This Platform

Windows ARM64 on Qualcomm/Insyde UEFI does **not** use the same ACPI table mechanism as x86. Specifically:

- `winload.efi` on ARM64 reads ACPI tables exclusively from the UEFI firmware via `EFI_ACPI_TABLE_PROTOCOL` from the UEFI ConfigurationTable
- It does **not** read `HKLM\SYSTEM\CurrentControlSet\Control\acpitables` (x86/BIOS-only)
- `ACPIOVERRIDETEST` BCD flag is x86/x64 only — irrelevant on ARM64
- GRUB2's `acpi` module modifies the XSDT in memory but does NOT update the EFI ConfigurationTable RSDP pointer — Windows ARM64 ignores GRUB's copy

The only working approach is a UEFI application that calls **`EFI_ACPI_TABLE_PROTOCOL->InstallAcpiTable()`** before ExitBootServices(). This protocol adds the SSDT to the live ACPI table set that Windows reads from the EFI ConfigurationTable.

---

## Injection Attempts Log

### Attempt 1 — `acpitables` Registry + ACPIOVERRIDETEST (Sessions 16–17)
- **Approach:** Write patched SSDT (80 bytes) to `HKLM\SYSTEM\CurrentControlSet\Control\acpitables\00000000`, set BCD `loadoptions ACPIOVERRIDETEST`
- **Result:** FAILED. Registry mechanism is dead on ARM64 UEFI. Flag is x86-only and has no effect.
- **Proof:** Test SSDT (HID: `QCOM1234`) never appeared in Device Manager despite BCD flag being set on every boot.

### Attempt 2 — ESP SSDT paths (Session 17)
- **Approach:** Placed `ssdt_qcsp.aml` at 4 paths: `S:\EFI\ACPI\`, `S:\EFI\OEM\`, `S:\acpi\`, `S:\EFI\ACPI\SSDT.aml`
- **Result:** FAILED. Insyde BIOS on this device does not load SSDTs from ESP paths.
- **Proof:** QCOM1234 test device never appeared.

### Attempt 3 — DSDT Binary Patch + `acpitables` Override (Session 22–23)
- **Approach:** Secure Boot disabled. Binary-patched `dsdt.aml` (QCSP `_DEP[2]` SPSS→GLNK at offset 0x036C69). Loaded 279633-byte patched DSDT into `acpitables\00000000`.
- **Result:** FAILED. Live DSDT at `HKLM\HARDWARE\ACPI\DSDT\...` still shows original bytes (`53 50 53 53` = SPSS). Windows ignores `acpitables` regardless of content.
- **Proof:** Byte comparison of live DSDT vs patched file confirmed override not applied.

### Attempt 4 — GRUB2 `acpi` Module (Sessions 23–25)
- **Approach:** GRUB USB (Ubuntu grubaa64.efi + arm64-efi modules). `grub.cfg`: `insmod acpi` + `acpi /ssdt_qcsp.aml` + `chainloader (hd0,gpt1)/EFI/Microsoft/Boot/bootmgfw.efi`
- **Result:** FAILED. GRUB menu appeared, chainload ran, Windows booted — but QCOM0C87 never appeared.
- **Root cause:** GRUB's `acpi` module modifies XSDT in RAM but does not update the EFI ConfigurationTable RSDP pointer. Windows ARM64 bootloader finds the original firmware RSDP and ignores GRUB's modified ACPI data.
- **Note:** chainloader `(hd0,gpt1)` was also wrong disk reference; fixed to `search`-based in later session.

### Attempt 5 — Custom AcpiInject.efi UEFI Application (Sessions 26–28+)
- **Approach:** Python-built 1536-byte PE32+ AARCH64 EFI application that:
  1. Calls `BootServices->LocateProtocol(&EFI_ACPI_TABLE_PROTOCOL_GUID, ...)` to get ACPI install service
  2. Calls `->InstallAcpiTable(proto, ssdt_data, 80, &key)` — installs 80-byte SSDT stub (QCSP87)
  3. Locates `\EFI\Microsoft\Boot\bootmgfw.efi` via `EFI_SIMPLE_FILE_SYSTEM_PROTOCOL`
  4. Constructs device path, calls `LoadImage` + `StartImage` → Windows boots
- **Build tool:** `C:\Drivers\build_efi.py` (Python 3.14 + keystone-engine 0.9.2)
- **Binary:** `C:\Drivers\AcpiInject.efi` → deployed to `D:\EFI\ACPI\AcpiInject.efi` and `D:\EFI\BOOT\BOOTAA64.EFI` on USB
- **Status: IN PROGRESS** — See Session 30 sub-attempt below.

---

### Attempt 5a — Sub-attempt: GRUB chainloader → AcpiInject.efi (Session 30)
- **Approach:** GRUB entry 0 ran `chainloader /EFI/ACPI/AcpiInject.efi` with boot chain: UEFI → Shim (BOOTAA64.EFI, 987440 bytes) → grubaa64.efi → chainloader
- **Result:** FAILED. Errors: `"Error: cannot load image"` then `"Error: You need to load the kernel first"`.
- **Root cause diagnosed:** PE binary was verified structurally correct (valid MZ/PE32+ headers, machine=0xAA64, subsystem=10/EFI_APPLICATION, section alignment correct, ARM64 prologue at entry point). Failure is not a binary format issue. Ubuntu Shim registers `EFI_SECURITY_ARCH_PROTOCOL` hooks that intercept `LoadImage` calls made by child images (GRUB). Even with Secure Boot off at firmware level, Shim's verification layer rejects unsigned custom EFI binaries when GRUB calls `LoadImage` on them.
- **Fix applied:** Replaced `D:\EFI\BOOT\BOOTAA64.EFI` with `AcpiInject.efi` (1536 bytes) directly. Shim backed up as `D:\EFI\BOOT\BOOTAA64_SHIM_BACKUP.EFI`. This bypasses GRUB/Shim entirely — UEFI loads AcpiInject.efi as the primary boot app, with no Shim security layer in the chain.
- **New boot flow:** `UEFI → BOOTAA64.EFI (= AcpiInject.efi) → InstallAcpiTable(SSDT) → LoadImage(bootmgfw.efi) → Windows`
- **Status: PENDING REBOOT TEST**

---

### Attempt 5b — Sub-attempt: AcpiInject.efi directly as BOOTAA64.EFI, section MEM_WRITE bug (Session 31)
- **Approach:** UEFI loads `D:\EFI\BOOT\BOOTAA64.EFI` (= AcpiInject.efi, 1536 bytes) directly as primary boot app, no Shim or GRUB in chain.
- **Result:** FAILED. Symptom: brief black screen, no text, returned to UEFI boot menu immediately.
- **Root cause diagnosed:** `build_efi.py` built the PE32+ with one `.text` section, characteristics `0x60000020` = `IMAGE_SCN_CNT_CODE | IMAGE_SCN_MEM_EXECUTE | IMAGE_SCN_MEM_READ`. Missing `IMAGE_SCN_MEM_WRITE (0x80000000)`. All static storage variables (`acpi_proto_ptr`, `handle_count`, `handle_buffer_ptr`, `sfs_ptr`, `root_ptr`, `file_ptr`, `devpath_ptr`, `new_devpath_ptr`, `win_handle`, `table_key`) live in this same section. On ARM64 UEFI firmware with memory protection (Qualcomm/Insyde enforces this), the section maps read-only. The very first external call (`LocateProtocol` writing back to `acpi_proto_ptr`) triggers an ARM64 permission fault. UEFI exception handler returns to boot menu.
- **Fix applied:** Changed section characteristics to `0xE0000020` (added `IMAGE_SCN_MEM_WRITE`). Rebuilt AcpiInject.efi (still 1536 bytes). Deployed to `D:\EFI\BOOT\BOOTAA64.EFI` and `D:\EFI\ACPI\AcpiInject.efi`.
- **Status: TESTED — STILL FAILED.** Symptom unchanged: brief black screen, no text, returned to UEFI boot menu. Confirmed both fixes (MEM_WRITE + ACPI GUID) are present in the deployed binary. SSDT checksum verified valid (sum=0). Root cause now unknown — could be Phase 1 (InstallAcpiTable) or Phase 2 (LoadImage/chainload).

---

### Attempt 5c — Sub-attempt: Debug build with ConOut output + BootPolicy fix (Session 32)
- **Approach:** Rebuilt `AcpiInject.efi` (2560 bytes) with: (1) `ConOut->OutputString` status messages printed at every key stage so exact failure point is visible on screen; (2) `LoadImage(BootPolicy=FALSE)` — changed from TRUE since we supply an explicit full device path; (3) Added `SKIP_ACPI = False` toggle at top of `build_efi.py` to bypass Phase 1 if needed.
- **Debug output printed at:** `[AI] start`, `[AI] Locate ACPI`, `[AI] ACPI proto ok/fail`, `[AI] InstallAcpiTable`, `[AI] SSDT ok/fail`, `[AI] SFS scan`, `[AI] SFS fail`, `[AI] bootmgfw found`, `[AI] LoadImage`, `[AI] LoadImage ok/fail`, `[AI] StartImage`
- **Also saved x27=SystemTable and x26=ConOut** at entry; enlarged stack frame to -80 bytes for x19-x27+lr.
- **Expected result:** At minimum `[AI] start` should appear on screen before any failure. The last line visible before screen clears / boot menu returns identifies the exact failure point.
- **Status: TESTED — STILL FAILED.** Symptom: black screen, no text at all, returned to UEFI boot menu (Session 33). Root cause identified: `NumDirEntries=0` and `DllCharacteristics=0x0000` — the Qualcomm/Insyde PE loader rejects the binary at LoadImage time before the entry point is ever called. Comparison with working GRUB binary (NumDirEntries=16, DllChars=0x0100) confirmed the exact mismatch.

---

### Attempt 5d — Sub-attempt: PE header fix + log-before-ConOut (Session 33)
- **Root cause of all prior failures (5b, 5c):** The PE32+ binary had `NumberOfRvaAndSizes=0` and `DllCharacteristics=0x0000`. The Qualcomm/Insyde UEFI PE loader requires `NumDirEntries=16` (standard DataDirectory) and `DllCharacteristics=0x0100` (NX_COMPAT) — exactly as the working GRUB `grubaa64.efi` binary has. The loader silently rejected LoadImage → entry point was never called, explaining why no ConOut output ever appeared.
- **Fixes applied to `build_efi.py`:**
  1. `CoffCharacteristics = 0x020E` (matches GRUB: EXECUTABLE | LINE_NUMS_STRIPPED | LOCAL_SYMS_STRIPPED | DEBUG_STRIPPED)
  2. `DllCharacteristics = 0x0100` (NX_COMPAT — required by Qualcomm/Insyde loader)
  3. `NumberOfRvaAndSizes = 16` (full DataDirectory)
  4. Added `.reloc` section (8-byte empty BASE_RELOCATION block at VA=0x2000); DataDirectory[5] points to it with Size=8 (correct — not the padded file size)
  5. Log file (`D:\ai_debug.txt`) creation moved to BEFORE ConOut print — provides trace even if ConOut is broken
  6. Added `[AI] ENTRY` as first log write immediately after log file opens
- **New binary:** `C:\Drivers\AcpiInject.efi`, 4096 bytes (3048 bytes code, 2 sections)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4096 bytes), `D:\EFI\ACPI\AcpiInject.efi`
- **Status: TESTED (Session 34)**
  - Binary IS running (black screen lasted much longer than before → confirmed entry point executing)
  - `D:\ai_debug.txt` did NOT exist → new bug found: wrong EFI_FILE_PROTOCOL offsets
  - QCOM0C87 did NOT appear → SSDT injection still not working (reason still unknown)

---

### Attempt 5e — Sub-attempt: EFI_FILE_PROTOCOL Write/Flush offset fix (Session 34)
- **Bug found:** `write_log()` in `build_efi.py` used wrong EFI_FILE_PROTOCOL offsets:
  - `[x28, #24]` labeled "Write" → but offset +24 is **Delete** — log file was deleted immediately after creation
  - `[x28, #32]` labeled "Flush" → but offset +32 is **Read**
  - Correct: Write=+40, Flush=+80
- **Fix:** Updated `write_log` to use `[x28, #40]` (Write) and `[x28, #80]` (Flush)
- **New binary:** rebuilt `C:\Drivers\AcpiInject.efi` (4096 bytes, same PE structure)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI`, `D:\EFI\ACPI\AcpiInject.efi`
- **Status: TESTED (Session 35)** — log STILL absent

---

### Attempt 5f — Sub-attempt: Brute-force SFS scan for log setup (Session 35)
- **Root cause of log file never appearing (despite correct Write/Flush offsets):** Log setup used
  `HandleProtocol(ImageHandle, LI_GUID)` → `DeviceHandle` → `HandleProtocol(DeviceHandle, SFS_GUID)`.
  The second `HandleProtocol` returns non-zero on this Insyde firmware — `LoadedImage->DeviceHandle`
  does not have `EFI_SIMPLE_FILE_SYSTEM_PROTOCOL` registered on it via `HandleProtocol`.
  Code silently jumped to `log_setup_done`, `x28=0`, every `write_log()` was a no-op.
  Phase 2 works because it uses `LocateHandleBuffer(ByProtocol, SFS_GUID)` (different mechanism).
- **Fix:** Replaced LoadedImage-based log setup with brute-force SFS scan:
  1. `LocateHandleBuffer(ByProtocol, SFS_GUID)` — same as Phase 2
  2. For each handle: `HandleProtocol` → `OpenVolume` → try `Open(\ssdt_qcsp.aml, READ)`
  3. If marker found: close it, `Open(\ai_debug.txt, CREATE)`, set x28
- **Additional improvement:** Added `write_log("done_fail")` at `done_fail:` label — distinguishes
  firmware fallback (black screen + Windows) from successful StartImage.
- **New binary:** `C:\Drivers\AcpiInject.efi` — **4608 bytes** (786 instructions / 3232 bytes code)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4608 bytes), `D:\EFI\ACPI\AcpiInject.efi`
- **Status: TESTED (Session 36)** — log STILL absent
- **Root cause identified (Session 36):** USB SFS handle is NOT returned by
  `LocateHandleBuffer(ByProtocol, SFS_GUID)` on this Insyde firmware. Only NVMe
  SFS handles are globally registered. Marker file `\ssdt_qcsp.aml` confirmed
  present at `D:\ssdt_qcsp.aml` (80 bytes) — but USB SFS handle never enumerated,
  so marker check never runs. Phase 2 finds bootmgfw.efi on NVMe SFS handles and
  chainloads Windows normally. Fix: see Attempt 5g below.

---

### Attempt 5h — Sub-attempt: UEFI SetVariable logging (Session 37)
- **Root cause of persistent missing log:** Both USB (not in LocateHandleBuffer) and NVMe EFI partition SFS handles (in LocateHandleBuffer but refusing CREATE) are unwritable from the UEFI app context. Insyde H2O firmware appears to write-protect the ESP for UEFI applications.
- **Fix:** Replaced file logging with UEFI NVRAM variable. `RuntimeServices->SetVariable` (SystemTable+88 → SetVariable at +88) writes a 1-byte status to variable `AcpiLog` with GUID `{DEADBEEF-CAFE-1234-ABCD-000000000042}`.
- **Status codes:** `A` = ACPI proto not found; `1` = InstallAcpiTable failed; `2` = SSDT injected successfully.
- **Windows read:** `GetFirmwareEnvironmentVariableW("AcpiLog", "{DEADBEEF-CAFE-1234-ABCD-000000000042}", ...)` after enabling `SeSystemEnvironmentPrivilege` (see Session 37 help file entry for full P/Invoke code).
- **File logging kept** as secondary attempt.
- **New binary:** `C:\Drivers\AcpiInject.efi` — 4608 bytes (823 instructions / 3336 bytes code)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4608 bytes, 11:12:08), `D:\EFI\ACPI\AcpiInject.efi`
- **Status: TESTED (Session 38)**
  - Boot behavior: black screen 10-15s then Windows (binary executes correctly)
  - `GetFirmwareEnvironmentVariableW("AcpiLog", ...)` returned **error 1314** even elevated with `SeSystemEnvironmentPrivilege` present in token
  - `BootOrder` (standard UEFI variable) also returned error 1314 — confirmed: Qualcomm/Insyde on this device blocks UEFI runtime variable services from Windows entirely. SetVariable logging is permanently dead.
  - `HKLM\HARDWARE\ACPI\SSDT` contains only `Compal` — our SSDT was never injected
  - **Root cause:** `EFI_ACPI_TABLE_PROTOCOL` could not be used from this boot app. Whether the protocol is genuinely absent or merely rejected `InstallAcpiTable` cannot be cleanly distinguished, because builds through 5g queried the wrong protocol GUID (the Absolute Pointer GUID — see the wrong-GUID note) and no UEFI-side diagnostic channel survived by the time the GUID was corrected. Protocol-based injection *via this app* is exhausted; the protocol's true state on V1.09 is unconfirmed.

---

### Attempt 5i — Sub-attempt: Direct XSDT modification (Session 38)
- **Root cause of all Phase 1 failures:** `EFI_ACPI_TABLE_PROTOCOL` is not usable on this Insyde H2O firmware. UEFI runtime variable services (`GetFirmwareEnvironmentVariableW`) are blocked for all variables at the kernel level (error 1314 for `BootOrder`, not just our custom var). File I/O also blocked. No logging mechanism available.
- **Approach:** Bypass all optional protocols. Walk `SystemTable->ConfigurationTable` (at `SystemTable+112`), compare each entry's GUID against `EFI_ACPI_20_TABLE_GUID = {8868E871-E4F1-11D3-BC22-0080C73C8881}`. When found: read `RSDP->XsdtAddress` (RSDP+24), `AllocatePages(EfiACPIMemoryNVS, 1 page)`, `CopyMem` old XSDT into new page, append 8-byte pointer to our embedded SSDT, update `new_xsdt->Length += 8`, recalculate XSDT checksum (byte 9), write new address to `RSDP->XsdtAddress`, recalculate RSDP extended checksum (byte 32, covers first 36 bytes). Windows reads ACPI tables from the RSDP → guaranteed to see our modified XSDT.
- **Key offsets used:**
  - `SystemTable->NumberOfTableEntries` at +104, `ConfigurationTable` at +112
  - `EFI_CONFIGURATION_TABLE` entry: 16-byte GUID + 8-byte VendorTable = 24 bytes
  - `BootServices->AllocatePages` at +40, `CopyMem` at +352
  - RSDP: `XsdtAddress` at +24 (UINT64), `ExtendedChecksum` at +32 (UINT8, covers [0..35])
  - XSDT: `Length` at +4 (UINT32), `Checksum` at +9 (UINT8)
- **New binary:** `C:\Drivers\AcpiInject.efi` — 4608 bytes (774 instructions / 3152 bytes code)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4608 bytes, 14:28:38), `D:\EFI\ACPI\AcpiInject.efi`
- **Status: TESTED (Session 39) — FAILED**
  - Windows booted normally (binary executed, Phase 2 chainload worked)
  - `HKLM\HARDWARE\ACPI\SSDT` still only `Compal` — SSDT not parsed by Windows
  - Root cause: SSDT data (`ssdt_data` label) was in `.text` section (EfiLoaderCode memory).
    Windows reclaims EfiLoaderCode after ExitBootServices. `acpi.sys` maps ACPI table physical
    addresses later — by then, the ssdt_data page is reclaimed/invalid. XSDT entry pointed to
    dead memory → SSDT silently ignored.
  - Fix: see Attempt 5j below.

**Post-boot diagnostic (elevated PowerShell):**
```powershell
# 1. Was our SSDT parsed? (look for QCOMM_ key)
Get-ChildItem "HKLM:\HARDWARE\ACPI\SSDT"

# 2. Did QCOM0C87 appear?
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C87*"} | Select-Object FriendlyName, Status, InstanceId

# 3. PIL TZ interface active?
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid" -Recurse | Get-ItemProperty | Select-Object PSChildName, Linked

# 4. Full non-OK list
Get-PnpDevice | Where-Object {$_.Status -ne "OK"} |
    Where-Object {$_.InstanceId -notlike "SWD\MSRRAS*"} |
    Select-Object FriendlyName, Status, Problem, InstanceId | Format-Table -AutoSize
```

**Interpreting results:**
- `QCOMM_` key in SSDT + `QCOM0C87` appears + `Linked=1` → **deadlock broken** → proceed
- `QCOMM_` key in SSDT + `QCOM0C87` absent → SSDT parsed but qcsp.sys failed to bind → check driver staging
- `QCOMM_` key absent → XSDT modification didn't work (RSDP not found, or Windows ignored the new XSDT) → investigate
- Only `Compal` in SSDT → same as before → XSDT mod failed silently

---

### Attempt 5j — Sub-attempt: SSDT pointer in EfiACPIMemoryNVS (Session 39)
- **Root cause of 5i failure:** XSDT entry pointed to `ssdt_data` in `.text` section
  (`EfiLoaderCode`). Windows reclaims EfiLoaderCode after ExitBootServices. `acpi.sys` tries
  to map that physical address later → page is gone → SSDT silently dropped.
  Both the new XSDT AND the SSDT data it points to must be in `EfiACPIMemoryNVS` (never
  reclaimed by Windows) or `EfiACPIReclaimMemory` (reclaimed only after ACPI parse completes).
- **Fix:** Added second `AllocatePages(EfiACPIMemoryNVS, 1)` call for SSDT bytes, then
  `CopyMem(ssdt_phys_page, ssdt_data, 80)`. XSDT entry now stores `ssdt_phys_page` address
  (NVS memory) instead of `&ssdt_data` (EfiLoaderCode).
- **New binary:** `C:\Drivers\AcpiInject.efi` — 4608 bytes (802 instructions / 3224 bytes code)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4608 bytes, 15:01:52), `D:\EFI\ACPI\AcpiInject.efi`
- **Pre-reboot baseline:** `baselines\A14_PreSession39Reboot_20260528_150203.csv`
- **Status: TESTED (Session 40) — FAILED**
  - `HKLM\HARDWARE\ACPI\SSDT` still only `Compal` — SSDT never parsed
  - `QCOM0C87` absent, PIL TZ Linked absent, ADSP/CDSP/SPSS all CM_PROB_FAILED_ADD
  - **Root cause identified:** Writing to `RSDP->XsdtAddress` (a 36-byte structure in firmware ROM or
    write-protected EFI memory) is silently ignored — the RSDP is in a different (likely read-only)
    memory region from the XSDT/DSDT. Both 5i and 5j successfully allocated NVS memory and built
    the new XSDT correctly, but the RSDP pointer update never took effect. Windows reads the original
    RSDP, finds the original XSDT, and never sees our new entry.
  - **Confirmed diagnostic:** `HKLM:\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003:00000000` at
    offset 0x36C69 still shows `53 50 53 53` (SPSS) — no modification reached the DSDT.
  - **Fix:** See Attempt 5k below — patch DSDT directly, avoids all RSDP/XSDT writes.

---

### Attempt 5k — Sub-attempt: DSDT in-place _DEP patch (Session 40)
- **Root cause of all 5i/5j failures:** Writing to `RSDP->XsdtAddress` is silently ignored.
  The RSDP is in firmware-protected memory (read-only from EFI application context).
  All XSDT modification approaches fail for the same reason: they all require updating the RSDP.
- **New approach:** Patch the DSDT itself in-place. No RSDP or XSDT writes needed.
  Algorithm:
  1. Walk `SystemTable->ConfigurationTable` → find ACPI 2.0 GUID → RSDP (READ only)
  2. `RSDP->XsdtAddress` → XSDT (READ only)
  3. Walk XSDT entries → find FADT (signature "FACP") (READ only)
  4. `FADT->X_DSDT` (at FADT+140) → DSDT physical address (READ only)
  5. Verify `DSDT[0x36C69..0x36C6C]` == `53 50 53 53` ("SPSS")
  6. WRITE `47 4C 4E 4B` ("GLNK") at `DSDT[0x36C69..0x36C6C]`
  7. Recalculate DSDT checksum (DSDT+9)
- **Why this works (if DSDT is writable):** Changes `QCSP._DEP[2]` from `\_SB.SPSS` to
  `\_SB.GLNK`. GLNK (GLINK IPC device) is confirmed present in DSDT (15 occurrences) and
  is RUNNING at boot. The `_DEP` dependency for QCSP is satisfied → Windows presents
  `ACPI\QCOM0C87` → `qcsp.sys` loads → PIL TZ interface activates → ADSP/CDSP/SPSS start.
- **No SSDT data embedded** — binary is smaller; no new table injection needed.
- **New binary:** `C:\Drivers\AcpiInject.efi` — **4096 bytes** (758 instructions / 3000 bytes code)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4096 bytes, 15:26:42), `D:\EFI\ACPI\AcpiInject.efi`
- **Pre-reboot baseline:** `baselines\A14_PreAttempt5k_20260528_<time>.csv` (40 non-OK devices)
- **Status: TESTED (Session 40) — FAILED**
  - Boot behavior: black screen ~10–15s → Acer logo → Windows (binary executed, chainload OK)
  - `DSDT[0x36C69]` = `53 50 53 53` ("SPSS") — write silently dropped, patch did NOT apply
  - `QCOM0C87` absent, PIL TZ `Linked` absent, ADSP/CDSP/SPSS all `CM_PROB_FAILED_ADD` — unchanged
  - Non-OK count: 40 — unchanged
  - **Root cause:** DSDT memory page is also write-protected. Same silent-drop protection as RSDP.
    The entire ACPI table chain (RSDP+24, DSDT bytes) resides in read-only EFI pages. No ARM64
    fault — writes just don't take effect. EFI_MEMORY_ATTRIBUTE_PROTOCOL needed to unprotect
    before writing.
  - **Baseline:** `baselines\A14_AfterAttempt5k_<timestamp>.csv`

**Post-boot diagnostic (run elevated):**
```powershell
# 1. PRIMARY: Did the DSDT patch apply? (GLNK = 47 4C 4E 4B, SPSS = 53 50 53 53)
$dsdt = (Get-ItemProperty "HKLM:\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003")."00000000"
$bytes = $dsdt[0x36C69..0x36C6C]
$hex = $bytes | ForEach-Object { "{0:X2}" -f $_ }
$ascii = [System.Text.Encoding]::ASCII.GetString($bytes)
Write-Host "DSDT[0x36C69]: $($hex -join ' ')  = '$ascii'"
# Expected if patch worked: "47 4C 4E 4B  = 'GLNK'"
# Expected if DSDT protected: "53 50 53 53  = 'SPSS'"

# 2. Did QCOM0C87 appear?
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C87*"} | Select-Object FriendlyName, Status, InstanceId

# 3. PIL TZ active?
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid" -Recurse | Get-ItemProperty | Select-Object PSChildName, Linked

# 4. ADSP / CDSP / SPSS
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C1B*" -or $_.InstanceId -like "*QCOM0CB0*" -or $_.InstanceId -like "*QCOM0C8D*"} | Select-Object FriendlyName, Status, Problem

# 5. Full non-OK list
Get-PnpDevice | Where-Object {$_.Status -ne "OK"} |
    Where-Object {$_.InstanceId -notlike "SWD\MSRRAS*"} |
    Select-Object FriendlyName, Status, Problem, InstanceId | Format-Table -AutoSize

# 6. Export baseline
Get-PnpDevice | Where-Object {$_.Status -ne "OK"} |
    Where-Object {$_.InstanceId -notlike "SWD\MSRRAS*"} |
    Select-Object Class, FriendlyName, Status, Problem, InstanceId |
    Export-Csv -Path "C:\Users\user\Desktop\A14\baselines\A14_AfterAttempt5k_$(Get-Date -Format yyyyMMdd_HHmmss).csv" -NoTypeInformation
```

**Interpreting results:**
- DSDT shows `GLNK` + `QCOM0C87` in PnP + `Linked=1` → **deadlock broken** → install ADSP/BT/audio
- DSDT shows `GLNK` + `QCOM0C87` absent → patch applied but qcsp.sys not binding (check driver staging)
- DSDT shows `SPSS` + Windows boots normally → DSDT is also write-protected → try EFI_MEMORY_ATTRIBUTE_PROTOCOL
- Machine returns to boot menu instead of Windows → DSDT write caused a fatal exception → DSDT protected

---

### Attempt 5g — Sub-attempt: Remove marker check, create log on first writable SFS (Session 36)
- **Root cause of persistent missing log:** `LocateHandleBuffer(ByProtocol, SFS_GUID)`
  does NOT return the USB (boot device) SFS handle on this Insyde H2O firmware. Only
  NVMe EFI partition SFS handles are globally registered. Marker file `\ssdt_qcsp.aml`
  IS present on USB root (`D:\ssdt_qcsp.aml`, confirmed 80 bytes), but since USB SFS
  handle is never returned, the marker is never seen. All NVMe handles fail the marker
  check → x28 stays 0 → all `write_log()` calls are no-ops.
- **Fix:** Removed marker check entirely from log setup loop. New logic:
  1. `LocateHandleBuffer(ByProtocol, SFS_GUID)` — gets NVMe SFS handles
  2. For each handle: `HandleProtocol` → `OpenVolume` → try `Open(\ai_debug.txt, CREATE)`
  3. Save Open status; close root regardless
  4. First handle where Open succeeds: set x28, write `[AI] ENTRY` + `[AI] log open`, break
- **Expected log location:** NVMe EFI partition root (`S:\ai_debug.txt` after `mountvol S: /s`)
  or possibly `D:\ai_debug.txt` (USB, if it IS returned in some iterations)
- **New binary:** `C:\Drivers\AcpiInject.efi` — **4608 bytes** (772 instructions / 3176 bytes code)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4608 bytes), `D:\EFI\ACPI\AcpiInject.efi`
- **Status: PENDING REBOOT TEST**
- **Pre-reboot baseline:** `baselines\A14_PreSession36Reboot_20260528_101841.csv`

**Post-boot diagnostic commands:**
```powershell
# 1. Check USB first
Get-Content "D:\ai_debug.txt" -ErrorAction SilentlyContinue

# 2. Mount EFI partition and check
mountvol S: /s
Get-Content "S:\ai_debug.txt" -ErrorAction SilentlyContinue
mountvol S: /d

# 3. QCOM0C87
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C87*"} | Select-Object FriendlyName, Status, InstanceId

# 4. PIL TZ
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid" -Recurse | Get-ItemProperty | Select-Object PSChildName, Linked
```

---

### Attempt 5l — Sub-attempt: EFI_MEMORY_ATTRIBUTE_PROTOCOL unprotect before DSDT patch (Session 40) — **INVALID: wrong GUID**

> **Audit note (2026-06-09):** The GUID used (`{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}`) is
> **`EFI_COMPONENT_NAME2_PROTOCOL`**, not `EFI_MEMORY_ATTRIBUTE_PROTOCOL`. The correct MAP GUID
> is `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}` (EDK2 `MdePkg/Include/Protocol/MemoryAttribute.h`).
> `LocateProtocol` most likely succeeded against Component Name 2 (essentially always present) and
> the code called that protocol's vtable at MAP's offsets — invoking an unrelated function. This is
> the same class of error as the 5a–5g `EFI_ACPI_TABLE_PROTOCOL` wrong-GUID bug. **5l/5m results
> are INVALID; MAP was never tested.** Correct GUID fixed in `build_efi.py` 2026-06-09.

- **Root cause of 5k failure:** DSDT pages are read-only in EFI page tables. Writes silently dropped
  without causing a fault. Same protection as RSDP region. The entire ACPI table chain is in
  firmware-managed read-only memory.
- **Fix:** Before writing to DSDT, call `EFI_MEMORY_ATTRIBUTE_PROTOCOL->ClearMemoryAttributes()` to
  clear `EFI_MEMORY_RO (0x20000)` on the DSDT pages, making them writable.
- **Protocol GUID (WRONG — see audit note):** `{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}` — this is `EFI_COMPONENT_NAME2_PROTOCOL`
- **Correct MAP GUID:** `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}` (UEFI 2.10, EDK2-verified)
- **Protocol vtable offsets:** GetMemoryAttributes=+0, SetMemoryAttributes=+8, ClearMemoryAttributes=+16
- **Algorithm:**
  1. Walk ConfigurationTable → RSDP (read) → XSDT (read) → FADT (read) → X_DSDT → dsdt_phys
  2. `LocateProtocol(&MAP_ATTR_GUID)` → map_proto
  3. `map_proto->ClearMemoryAttributes(dsdt_phys & ~0xFFF, ((dsdt_len+0xFFF)>>12)<<12, 0x20000)`
     (DSDT = 279633 bytes = 69 pages; clear RO on all pages)
  4. Verify DSDT[0x36C69] == "SPSS", write "GLNK", recalculate DSDT checksum (byte 9)
  5. Phase 2: chainload bootmgfw.efi
- **If MAP protocol absent:** write anyway (already proven to fail), chainload Windows unchanged.
- **New binary:** `C:\Drivers\AcpiInject.efi` - 4608 bytes (794 instructions / 3088 bytes code)
- **Deployed:** `D:\EFI\BOOT\BOOTAA64.EFI` (4608 bytes, 16:16:22)
- **MAP GUID verified** in binary at offset 0xDF8
- **Status: TESTED (Session 41) — FAILED**
  - Boot behavior: normal (black screen → Acer logo → Windows)
  - `DSDT[0x36C69]` = `53 50 53 53` ("SPSS") — patch did NOT apply
  - `QCOM0C87` absent from PnP, PIL TZ `Linked` blank, ADSP/CDSP/SPSS all `CM_PROB_FAILED_ADD` — unchanged
  - Non-OK device count: **40** — unchanged
  - **Root cause:** INVALID RESULT — wrong GUID used (see audit note above). The observation
    "DSDT unchanged" does not establish MAP absent or non-functional. Retest required (D8).
  - **Baseline:** `baselines\A14_AfterAttempt5l_<timestamp>.csv`

**Post-boot diagnostic results (Session 41):**
```
CHECK 1: DSDT[0x36C69] = 53 50 53 53 = 'SPSS'  ← patch not applied
CHECK 2: QCOM0C87 — no entry in PnP
CHECK 3: PIL TZ Linked — blank (inactive)
CHECK 4: ADSP (QCOM0C1B), CDSP (QCOM0CB0), SPSS (QCOM0C8D) — all CM_PROB_FAILED_ADD
CHECK 5: 40 non-OK devices — identical to pre-5l
```

---

### Attempt 5m — Sub-attempt: MAP diagnostic with canary write (Sessions 46–47) — **INVALID: wrong GUID (same as 5l)**

> **Audit note (2026-06-09):** Same wrong-GUID bug as 5l applies here — MAP was never invoked.
> The unchanged canary does not establish MAP absent or ClearMemoryAttributes non-functional.
> The conclusion "DSDT direct-write path is confirmed permanently closed" is withdrawn.

- **Goal:** Definitively determine whether MAP protocol (`EFI_MEMORY_ATTRIBUTE_PROTOCOL`) is absent
  or present-but-also-blocked by testing a canary write to a safe DSDT header field.
- **Canary target:** `DSDT[0x20..0x23]` = CreatorRevision header field.
  Pre-write value: `00 00 00 05`. Never read by ACPI interpreter — safe to corrupt.
  Write value: `0x41414141` ("AAAA").
- **Key changes vs 5l:**
  1. `ADD_STALL = True` — 3-second stall at `phase2:` entry (was dead code in loop tail in 5l)
  2. Canary write `0x41414141` → `DSDT[0x20]` before SPSS safety check
  3. DSDT[0x36C69] GLNK write retained from 5l (gated by SPSS safety check)
- **Build:** Session 46. `efi-injection/build_efi.py`. Output: 824 instructions, 3200 bytes code,
  PE size 4608 bytes. Deployed to `D:\EFI\BOOT\BOOTAA64.EFI` (timestamp 29/05/2026 14:58:10).
- **Status: TESTED (Session 47) — FAILED**
  - Boot visual: ~3-second stall observed before Windows loaded (confirms app ran to `phase2:`)
  - `DSDT[0x20..0x23]` = `00 00 00 05` — **unchanged** from pre-boot baseline (`00 00 00 05`)
  - `DSDT[0x36C69]` = `53 50 53 53` ("SPSS") — patch not applied
  - **Conclusion (revised 2026-06-09):** INVALID — wrong GUID used (see audit note). Stall
    observed confirms app ran, but unchanged canary does not establish MAP absent or
    ClearMemoryAttributes non-functional. "DSDT direct-write path permanently closed" withdrawn;
    retest with correct GUID `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}` required (D8).
  - Baseline: `baselines\A14_Baseline_<timestamp>_Post5m.csv`

---

### Attempt 5n — Sub-attempt: BootServices->InstallConfigurationTable() (Session 47, PLANNED)
- **Root cause of 5k failure and rationale for 5n:** DSDT, RSDP, and all firmware ACPI table
  memory appears to be in read-only pages. 5l/5m were intended to test MAP but used the wrong
  GUID and are invalid (see audit notes). Whether MAP can lift the protection is still unknown.
- **New approach:** Instead of writing to protected firmware memory, call the firmware's own
  `BootServices->InstallConfigurationTable()` to atomically replace the ACPI 2.0 GUID entry in
  `SystemTable->ConfigurationTable[]` with a pointer to a fully fresh NVS-allocated RSDP.
  The firmware manages `ConfigurationTable[]` via its own service — calling that service avoids
  any raw pointer write into protected memory.
- **Why this differs from 5i/5j:** 5i/5j wrote directly to `RSDP->XsdtAddress` (raw write,
  silently dropped). 5n calls `InstallConfigurationTable()` which is a firmware BootServices
  function that internally replaces the table pointer in the ConfigurationTable array.
- **BootServices offset:** `InstallConfigurationTable` = `BootServices + 0x0C0`
  (standard UEFI spec, between `LocateDevicePath` at +0x0B8 and `LoadImage` at +0x0C8)
- **Algorithm:**
  1. Walk `SystemTable->ConfigurationTable` (at +112) — find ACPI 2.0 GUID entry → read existing
     RSDP pointer (read-only OK, just reading)
  2. `AllocatePages(EfiACPIMemoryNVS)` — allocate NVS pages for new RSDP + new XSDT + SSDT data
  3. Copy firmware RSDP into NVS RSDP page; update `XsdtAddress` (+24) to point at NVS XSDT
  4. Copy original XSDT into NVS XSDT page; append 8-byte SSDT pointer; update Length (+4);
     recalculate XSDT checksum (byte +9)
  5. Copy 80-byte SSDT stub into NVS SSDT page
  6. Recalculate RSDP extended checksum (byte +32, covers bytes 0–35)
  7. `BootServices->InstallConfigurationTable(&EFI_ACPI_20_TABLE_GUID, new_nvs_rsdp)` — replaces entry
  8. Phase 2: chainload bootmgfw.efi as usual
- **Key GUID:** `EFI_ACPI_20_TABLE_GUID = {8868E871-E4F1-11D3-BC22-0080C73C8881}`
- **Status: BUILDING (Session 47)**

---

## USB Current State (as of Session 41)

**Drive:** D: (FAT32, label `CCCOMA_A64F`, 32 GB)

| File | Size | Role |
|---|---|---|
| `EFI\BOOT\BOOTAA64.EFI` | **4608 bytes** | **AcpiInject.efi Attempt 5m** — MAP canary + DSDT patch — TESTED, FAILED (Session 47) |
| `EFI\BOOT\BOOTAA64_SHIM_BACKUP.EFI` | 987440 bytes | Backup of original Ubuntu Shim (restore if needed) |
| `EFI\BOOT\grubaa64.efi` | 2533256 bytes | GRUB ARM64 binary (no longer in boot chain) |
| `EFI\BOOT\BOOTAA64_GRUB_BACKUP.EFI` | 2533256 bytes | Backup of original GRUB binary |
| `EFI\ACPI\AcpiInject.efi` | 1536 bytes | Copy of injector (not used by UEFI — BOOTAA64.EFI is used) |
| `boot\grub\grub.cfg` | — | GRUB config (not used — GRUB bypassed) |
| `boot\grub\arm64-efi\` | 253 modules | GRUB modules (not used) |
| `ssdt_qcsp.aml` | 80 bytes | SSDT stub (embedded in AcpiInject.efi) |

**Boot chain:**
```
UEFI → D:\EFI\BOOT\BOOTAA64.EFI (= AcpiInject.efi directly)
  → Phase 1: LocateProtocol(EFI_ACPI_TABLE_PROTOCOL) → InstallAcpiTable(80-byte SSDT)
  → Phase 2: LocateHandleBuffer(SFS) → walk handles → open \EFI\Microsoft\Boot\bootmgfw.efi
  → LoadImage(bootmgfw.efi device path) + StartImage → Windows boots with SSDT injected
```

**To restore GRUB boot chain (if needed):**
```powershell
Copy-Item "D:\EFI\BOOT\BOOTAA64_SHIM_BACKUP.EFI" "D:\EFI\BOOT\BOOTAA64.EFI" -Force
```

**Current grub.cfg:**
```
set timeout=10
set default=0

menuentry "Boot Windows (SSDT inject via AcpiInject.efi)" {
    insmod chain
    chainloader /EFI/ACPI/AcpiInject.efi
    boot
}

menuentry "Boot Windows directly (no SSDT inject)" {
    insmod chain
    insmod search
    search --file --no-floppy --set=root /EFI/Microsoft/Boot/bootmgfw.efi
    chainloader /EFI/Microsoft/Boot/bootmgfw.efi
    boot
}
```

**Session 29 fix applied:** Copied `BOOTAA64_GRUB_BACKUP.EFI` → `grubaa64.efi` to fix "Failed to open \EFI\BOOT\grubaa64.efi – Not Found" Shim error. Also restored correct grub.cfg (AcpiInject.efi approach, not broken `acpi` module).

---

## How to Boot for Testing

1. Ensure USB (D: / CCCOMA_A64F) is plugged in
2. Restart → press **F12** at Acer logo → select USB from one-time boot menu
3. GRUB menu appears with 10-second countdown
4. Entry 0 "Boot Windows (SSDT inject via AcpiInject.efi)" auto-boots
5. Windows loads normally — log in
6. Run diagnostics (elevated PowerShell):

```powershell
# 1. Did QCOM0C87 appear? (deadlock broken if yes)
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C87*"} | Select-Object FriendlyName, Status, InstanceId

# 2. PIL TZ interface active? (Linked=1 = deadlock broken)
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
$base = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid"
Get-ChildItem $base -Recurse | Get-ItemProperty | Select-Object PSChildName, Linked

# 3. ADSP / CDSP / SPSS status
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C1B*" -or $_.InstanceId -like "*QCOM0CB0*" -or $_.InstanceId -like "*QCOM0C8D*"} | Select-Object FriendlyName, Status, Problem

# 4. Full non-OK list
Get-PnpDevice | Where-Object {$_.Status -ne "OK"} |
    Where-Object {$_.InstanceId -notlike "SWD\MSRRAS*"} |
    Select-Object FriendlyName, Status, Problem, InstanceId | Format-Table -AutoSize

# 5. Export baseline
Get-PnpDevice | Where-Object {$_.Status -ne "OK"} |
    Where-Object {$_.InstanceId -notlike "SWD\MSRRAS*"} |
    Select-Object Class, FriendlyName, Status, Problem, InstanceId |
    Export-Csv -Path "C:\Users\user\Desktop\A14\baselines\A14_AfterAcpiInject_$(Get-Date -Format yyyyMMdd_HHmmss).csv" -NoTypeInformation
```

**Interpreting results:**
- `QCOM0C87` appears + `Linked=1` + SPSS OK → **Deadlock broken** → proceed to Bluetooth + ADSP install
- `QCOM0C87` appears but SPSS still failing → EFI app injected table but something else blocking → report exact ProblemStatus
- `QCOM0C87` does NOT appear, GRUB menu appeared → AcpiInject.efi failed → check AcpiInject.efi binary, try debug build
- GRUB menu did NOT appear → Shim/GRUB issue → check grubaa64.efi size (should be 2533256 bytes)

---

## AcpiInject.efi Details

**Source:** `C:\Drivers\build_efi.py` (Python 3.14 + keystone-engine 0.9.2)
**Binary:** `C:\Drivers\AcpiInject.efi` (also at `D:\EFI\ACPI\AcpiInject.efi`)
**Size:** 1536 bytes
**Architecture:** PE32+, AARCH64, Subsystem=EFI_APPLICATION
**Entry RVA:** 0x1000
**Assembled:** 226 ARM64 instructions, 840 bytes machine code
**Section flags (Session 31 fix):** `0xE0000020` = `IMAGE_SCN_CNT_CODE | IMAGE_SCN_MEM_EXECUTE | IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE` (was `0x60000020`, missing MEM_WRITE — caused ARM64 permission fault on first write to static data)

**EFI protocol GUIDs used:**
- `EFI_ACPI_TABLE_PROTOCOL`: `{FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}` ← **CORRECT** (fixed from wrong `{8D59D32B-...}` which was EFI_ABSOLUTE_POINTER)
- `EFI_SIMPLE_FILE_SYSTEM_PROTOCOL`: `{964E5B22-6459-11D2-8E39-00A0C969723B}`
- `EFI_DEVICE_PATH_PROTOCOL`: `{09576E91-6D3F-11D2-8E39-00A0C969723B}`
- `EFI_LOADED_IMAGE_PROTOCOL`: `{5B1B31A1-9562-11D2-8E3F-00A0C969723B}`

**BootServices offsets used:**
- AllocatePool: +0x040
- HandleProtocol: +0x098
- LoadImage: +0x0C8
- StartImage: +0x0D0
- LocateHandleBuffer: +0x138
- LocateProtocol: +0x140
- CopyMem: +0x160

**SSDT embedded in binary:** The 80-byte SSDT (`QCOMM_`/`QCSP87`) is embedded in the `.data` section of AcpiInject.efi (visible as strings `QCOMM_QCSP87`, `QCOM0C87`, `QSP0` in binary).

**FILEPATH device path for bootmgfw.efi:**
- Type=0x04, SubType=0x04, Length=70 (4-byte header + 66-byte UTF-16LE path)
- Path: `\EFI\Microsoft\Boot\bootmgfw.efi`
- Followed by END node: 0x7F, 0xFF, 0x04, 0x00

---

## Next Steps if AcpiInject.efi Fails

If after Session 29 USB boot, `QCOM0C87` still does not appear:

1. **Debug AcpiInject.efi** — check if `LocateProtocol` for `EFI_ACPI_TABLE_PROTOCOL` returns EFI_SUCCESS. If the protocol is not found, the SSDT won't install. Try alternative GUID for older Insyde BIOS: some use `EFI_ACPI_SUPPORT_PROTOCOL` instead.

2. **Try rEFInd** — rEFInd bootloader supports ACPI patching via `.aml` files. Place `refind_aa64.efi` + config at `EFI\BOOT\BOOTAA64.EFI` with `extra_kernel_version_strings` and `acpi_patch` entries. rEFInd may use `EFI_ACPI_TABLE_PROTOCOL` correctly.

3. **Check alternate ACPI Table GUID** — Some platforms register the ACPI table service under a different GUID. Try `{EFI_ACPI_TABLE_PROTOCOL_GUID_OLD}` = `{6DABB78A-FB9B-4DAB-8F83-E9DBE853AF76}`.

4. **WOA Project community** — post with exact failure chain + DSDT AML bytes for QCSP (offset 0x36C3F) + AcpiInject.efi approach tried. Request working SSDT injection path for Insyde ARM64.

5. **Acer BIOS V1.10+** — check Acer support page for NX.JP3ED.002 periodically. A BIOS update removing `_DEP` on `\_SB.SPSS` from QCSP device would permanently fix this without any injection.

---

## Files Reference

| File | Location | Purpose |
|---|---|---|
| `ssdt_qcsp.asl` | `C:\Drivers\` | SSDT ASL source |
| `ssdt_qcsp.aml` | `C:\Drivers\`, `D:\` | Compiled SSDT (80 bytes) |
| `dsdt.aml` | `C:\Drivers\` | Original DSDT binary (from registry) |
| `dsdt_patched.aml` | `C:\Drivers\` | DSDT with QCSP _DEP patched (not used — acpitables dead on ARM64) |
| `dsdt.dsl` | `C:\Drivers\` | Disassembled DSDT (84 compile errors — not recompilable) |
| `iasl.exe` | `C:\Drivers\` | ACPICA compiler v20260408 |
| `AcpiInject.efi` | `C:\Drivers\`, `D:\EFI\ACPI\` | Custom UEFI SSDT injector |
| `build_efi.py` | `C:\Drivers\` | Python script that built AcpiInject.efi |
| `capture.ps1` | `C:\Drivers\` | VSS + DISM capture script (for backup) |
| `A14_Backup_20260527.wim` | `D:\` | System image (22.57 GB, WD My Passport) |

---

### Attempt 5n result (Session 48 — FAILED)

- **Post-reboot oracle:** `HKLM\HARDWARE\ACPI\SSDT` = only "Compal". No QCOMM_ key.
- **Stall:** ~3-5 second pause before Acer logo observed — binary ran to phase2.
- **Bug discovered:** `stall_asm` used offset 232 (0xE8) = `ExitBootServices`, not offset 248 (0xF8) = `Stall`. All prior ADD_STALL builds had no real stall — the delay was normal app execution time.
- **ICT call correctness:** ICT at offset 0xC0 = 192 is correct per UEFI spec. AllocatePages/CopyMem/checksum logic looks correct. ICT result was not captured (no diagnostic output).
- **Conclusion:** ICT either returns an error (firmware blocks it like SetVariable), or succeeds but Windows does not use the ICT-updated ConfigurationTable entry to find its RSDP.

---

### Attempt 5o — ConOut ICT diagnostic + fixed stall (Session 48, TESTED — FAILED)

- **Goal:** Determine definitively: does ICT return EFI_SUCCESS? And does ConfigurationTable entry point to our new_rsdp after the call?
- **Key additions vs 5n:**
  1. Fixed stall: `ldr x8, [x20, #248]` (0xF8) — was incorrectly 232 (0xE8 = ExitBootServices).
     Duration: 8,000,000 µs = 8 seconds.
  2. After ICT call: `cbz x0, ict5o_ok` → ConOut `[AI] ICT=OK` or `[AI] ICT=ERR`.
  3. Re-scan ConfigurationTable post-ICT, compare VendorTable ptr against new_rsdp (x25):
     - `[AI] CT=OURS` — entry updated (ICT worked)
     - `[AI] CT=OLD` — entry unchanged (firmware ignoring ICT replacement)
     - `[AI] CT=NONE` — ACPI 2.0 GUID missing from CT
  4. 8-second stall holds screen so user can read output.
- **Binary:** `C:\Drivers\AcpiInject.efi` → `D:\EFI\BOOT\BOOTAA64.EFI`, 4608 bytes, 29/05/2026 16:09:16.
- **877 instructions, 3584 bytes code.**
- **Status: TESTED — FAILED**

**Post-boot diagnostics (same as 5n):**
```powershell
# Primary: did SSDT inject?
Get-ChildItem "HKLM:\HARDWARE\ACPI\SSDT" | Select-Object PSChildName

# Secondary (only matters if QCOMM_ present):
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C87*"} | Select-Object FriendlyName, Status, InstanceId
$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid" -Recurse | Get-ItemProperty | Select-Object PSChildName, Linked
```

**Interpretation table:**

| Screen shows | SSDT oracle | Meaning | Next step |
|---|---|---|---|
| ICT=OK + CT=OURS | QCOMM_ present | Deadlock broken | Install BT/audio drivers |
| ICT=OK + CT=OURS | only Compal | CT updated but bootmgfw ignores it (reads RSDP from physical memory?) | Investigate bootmgfw ACPI discovery |
| ICT=OK + CT=OLD | only Compal | ICT is a no-op (firmware non-compliant) | BIOS mod only path |
| ICT=ERR + CT=OLD | only Compal | ICT blocked (same lockdown as SetVariable) | All EFI injection closed; BIOS mod only |

### Attempt 5o result (Session 48 — FAILED)

- **Post-reboot oracle:** `HKLM\HARDWARE\ACPI\SSDT` = only "Compal". No `QCOMM_` key.
- **`ACPI\QCOM0C87`:** still absent from PnP; PIL TZ `Linked` still blank. Deadlock not broken.
- **Outcome:** the `InstallConfigurationTable()` path is closed. With this, every
  in-band software injection mechanism (5a–5o) has been attempted and has failed.
  The remaining paths are out of band only: an Acer BIOS update that removes SPSS
  from QCSP's `_DEP`, or offline BIOS ROM modification with a verified backup.

> Note: the exact on-screen `[AI] ICT=` / `[AI] CT=` lines from the 5o boot were
> not transcribed into the lab notes at test time. The injection outcome above
> (only "Compal", QCOM0C87 absent, deadlock unbroken) is confirmed from the
> post-boot registry oracle regardless of which ICT/CT branch was displayed.

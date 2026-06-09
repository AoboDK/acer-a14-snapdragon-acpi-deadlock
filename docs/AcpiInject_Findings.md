# AcpiInject.efi / build_efi.py Findings

> Snapshot analysis of `build_efi.py`. The findings below identified the GUID bug;
> subsequent attempts 5i–5l in [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md)
> revealed the deeper read-only memory blocker. See [`FINDINGS.md §8`](FINDINGS.md)
> for the synthesised story; see [`INDEX.md`](INDEX.md) for navigation.

Scope: Compare the uploaded `build_efi.py` from `build_efi.zip` against the tracking document `EFI_Injection_Tracking.md` and identify why the current SSDT injection path is not working.

## Executive summary

The current failure is most likely caused by a bad protocol GUID in `build_efi.py`.

The code intends to locate `EFI_ACPI_TABLE_PROTOCOL`, then call its first function pointer, `InstallAcpiTable()`, to inject the 80-byte SSDT before chainloading Windows. However, the GUID currently embedded as `ACPI_GUID` is not the ACPI table protocol GUID. It is the GUID for `EFI_ABSOLUTE_POINTER_PROTOCOL`.

This means the app either:

1. fails `LocateProtocol()` and silently skips ACPI injection, or
2. accidentally locates an unrelated Absolute Pointer protocol and calls the wrong function pointer as if it were `InstallAcpiTable()`.

Either outcome prevents the SSDT from being installed. That would explain why `ACPI\QCOM0C87` still does not appear and why the expected driver cascade never starts.

## Files reviewed

- `EFI_Injection_Tracking.md`
- `build_efi.zip`
  - extracted file: `build_efi.py`

## Intended boot flow from the tracking document

The intended working path is:

```text
UEFI -> BOOTAA64.EFI (= AcpiInject.efi directly)
  -> LocateProtocol(EFI_ACPI_TABLE_PROTOCOL)
  -> InstallAcpiTable(80-byte SSDT)
  -> LocateHandleBuffer(SIMPLE_FILE_SYSTEM)
  -> find \EFI\Microsoft\Boot\bootmgfw.efi
  -> LoadImage(bootmgfw.efi)
  -> StartImage(bootmgfw.efi)
  -> Windows boots with the injected SSDT visible
```

The SSDT goal is to create a dependency-free device:

```text
\_SB.QSP0
_HID = "QCOM0C87"
_UID = 1
_STA = 0x0F
```

Expected result if injection works:

```text
ACPI\QCOM0C87 appears
-> qcsp.sys loads
-> PIL TZ interface Linked=1
-> SPSS AddDevice succeeds
-> original QCSP dependency can resolve
-> ADSP/CDSP/Bluetooth/audio/battery/GPU blockers may clear
```

## Finding 1 - Definite bug: wrong ACPI protocol GUID

### Code currently present

In the uploaded `build_efi.py`:

```python
ACPI_GUID = pack_guid(0x8D59D32B, 0xC655, 0x4AE9,
                      0x9B, 0x15, 0xF2, 0x59, 0x04, 0x99, 0x2A, 0x43)
```

The same value is also listed in `EFI_Injection_Tracking.md` as:

```text
EFI_ACPI_TABLE_PROTOCOL: {8D59D32B-C655-4AE9-9B15-F25904992A43}
```

### Why this is wrong

The actual UEFI `EFI_ACPI_TABLE_PROTOCOL_GUID` is:

```c
{ 0xffe06bdd, 0x6107, 0x46a6,
  { 0x7b, 0xb2, 0x5a, 0x9c, 0x7e, 0xc5, 0x27, 0x5c } }
```

The GUID currently used by the code:

```text
{8D59D32B-C655-4AE9-9B15-F25904992A43}
```

is `EFI_ABSOLUTE_POINTER_PROTOCOL_GUID`, not `EFI_ACPI_TABLE_PROTOCOL_GUID`.

### Correct Python replacement

Replace the current `ACPI_GUID` block with:

```python
ACPI_GUID = pack_guid(0xffe06bdd, 0x6107, 0x46a6,
                      0x7b, 0xb2, 0x5a, 0x9c, 0x7e, 0xc5, 0x27, 0x5c)
```

Because `pack_guid()` uses:

```python
struct.pack("<IHH8B", a, b, c, *d)
```

it correctly emits EFI in-memory GUID layout.

### Current wrong bytes

```text
2b d3 59 8d 55 c6 e9 4a 9b 15 f2 59 04 99 2a 43
```

### Correct bytes

```text
dd 6b e0 ff 07 61 a6 46 7b b2 5a 9c 7e c5 27 5c
```

## Finding 2 - Runtime behavior caused by the bad GUID

The key Phase 1 assembly is:

```asm
// Phase 1: Install SSDT (ignore errors)
ldr  x8,  [x20, #320]      // BootServices->LocateProtocol
adr  x0,  acpi_guid        // currently wrong GUID
mov  x1,  xzr
adr  x2,  acpi_proto_ptr
blr  x8
cbnz x0,  phase2           // if LocateProtocol fails, skip injection
ldr  x25, acpi_proto_ptr
ldr  x8,  [x25, #0]        // intended: InstallAcpiTable
mov  x0,  x25
adr  x1,  ssdt_data
mov  x2,  #80
adr  x3,  table_key
blr  x8
```

With the wrong GUID, there are two likely outcomes.

### Outcome A - LocateProtocol fails

If the firmware does not expose Absolute Pointer protocol, then `LocateProtocol()` returns an error and the app branches to `phase2`.

Result:

```text
No SSDT installed
-> Windows still boots
-> QCOM0C87 does not appear
-> Linked remains missing/0
-> deadlock remains
```

This is the quiet failure case.

### Outcome B - LocateProtocol succeeds for Absolute Pointer

If the firmware does expose an Absolute Pointer protocol, then `LocateProtocol()` may return success, but `acpi_proto_ptr` points to an unrelated protocol structure.

Then the code does:

```asm
ldr x8, [x25, #0]
blr x8
```

It treats the first Absolute Pointer function pointer as if it were `InstallAcpiTable()`.

Result could be:

```text
Wrong function called with wrong arguments
-> EFI error
-> undefined behavior
-> possible immediate return to firmware boot menu
-> no SSDT installed
```

This is the dangerous failure case.

## Finding 3 - The Session 31 MEM_WRITE fix is present in the uploaded code

The uploaded `build_efi.py` uses:

```python
sec = struct.pack("<8sIIIIIIHHI",
    b".text\x00\x00\x00",
    section_vsize, section_vaddr,
    section_rawsz, HDR_SIZE,
    0, 0, 0, 0, 0xE0000020)
```

`0xE0000020` means:

```text
IMAGE_SCN_CNT_CODE
IMAGE_SCN_MEM_EXECUTE
IMAGE_SCN_MEM_READ
IMAGE_SCN_MEM_WRITE
```

This matches the documented Session 31 fix. Since the code stores variables such as `acpi_proto_ptr`, `handle_count`, `handle_buffer_ptr`, `sfs_ptr`, `root_ptr`, `file_ptr`, `devpath_ptr`, `new_devpath_ptr`, `win_handle`, and `table_key` inside the same section, the write bit is needed.

Conclusion: the missing `MEM_WRITE` bug appears fixed in the uploaded builder.

## Finding 4 - Boot Services offsets look internally consistent

The assembly uses these Boot Services offsets:

```text
AllocatePool         0x040 / 64
HandleProtocol       0x098 / 152
LoadImage            0x0C8 / 200
StartImage           0x0D0 / 208
LocateHandleBuffer   0x138 / 312
LocateProtocol       0x140 / 320
CopyMem              0x160 / 352
```

These match the offsets listed in the tracking document and are consistent with the UEFI Boot Services table layout for the calls being made.

Conclusion: I do not see an obvious Boot Services offset mismatch in the uploaded code.

## Finding 5 - Device path construction looks plausible

The code builds the bootmgfw file path as:

```python
bootmgfw_utf16 = r"\EFI\Microsoft\Boot\bootmgfw.efi".encode("utf-16-le") + b"\x00\x00"
assert len(bootmgfw_utf16) == 66
```

The generated file path node is:

```text
Type    = 0x04
SubType = 0x04
Length  = 70 bytes = 4-byte node header + 66-byte UTF-16 path
```

Then it appends:

```text
END node = 0x7F, 0xFF, 0x04, 0x00
```

This matches the tracking document.

Conclusion: the file path node is likely not the primary bug.

## Finding 6 - `InstallAcpiTable()` errors are ignored

The code comment says:

```asm
// Phase 1: Install SSDT (ignore errors)
```

After calling the intended `InstallAcpiTable()` function, the return status in `x0` is not checked:

```asm
blr  x8

phase2:
    // continue chainloading Windows regardless
```

This makes debugging much harder. Even after fixing the GUID, the app could fail injection for a different reason and still boot Windows normally.

Recommended improvement:

- Check `x0` after `InstallAcpiTable()`.
- If nonzero, display a visible error or return a distinct EFI status.
- Ideally print the failing phase and status code using `ConOut->OutputString()`.

Minimal logic change:

```asm
blr  x8
cbnz x0, done_fail
```

This is not ideal for normal daily use because it prevents Windows from booting if injection fails, but it is useful for the next debugging build.

## Finding 7 - No visible debug output means black-screen-return is ambiguous

The direct `BOOTAA64.EFI` path currently has no console logging. Therefore, this symptom:

```text
brief black screen -> no text -> returned to UEFI boot menu
```

cannot distinguish between:

- PE loader problem
- exception during protocol lookup
- exception during wrong protocol function call
- ACPI table install failure
- SFS handle enumeration failure
- bootmgfw path not found
- LoadImage failure
- StartImage failure

Recommended next debug build:

Print one short status line before and after each stage:

```text
[AI] start
[AI] BS ok
[AI] Locate ACPI: <status>
[AI] Install SSDT: <status>
[AI] Locate SFS: <status>
[AI] bootmgfw found
[AI] LoadImage: <status>
[AI] StartImage: <status>
```

A one-line status before each operation would make the next failure obvious.

## Finding 8 - Tracking document has a stale GRUB test instruction

The current USB state says:

```text
EFI\BOOT\BOOTAA64.EFI = AcpiInject.efi directly
GRUB is no longer in boot chain
```

But the later testing section still says:

```text
GRUB menu appears with 10-second countdown
```

That is no longer expected after replacing `BOOTAA64.EFI` with `AcpiInject.efi`.

Correct expectation for the current direct boot path:

```text
F12 USB boot
-> AcpiInject.efi runs directly
-> no GRUB menu
-> either Windows starts, or firmware returns to boot menu
```

If a GRUB menu appears, you are not testing the direct `AcpiInject.efi` path.

## Finding 9 - `LoadImage(TRUE, ...)` is probably not the primary failure, but `FALSE` is cleaner

The current code calls:

```asm
// LoadImage(TRUE, ImageHandle, NewDevPath, NULL, 0, &win_handle)
mov  x0,  #1
```

That passes `BootPolicy = TRUE`.

Since the code is constructing an explicit full device path to `bootmgfw.efi`, `BootPolicy = FALSE` is cleaner and more conventional:

```asm
// LoadImage(FALSE, ImageHandle, NewDevPath, NULL, 0, &win_handle)
mov  x0,  xzr
```

I do not consider this the root cause. The wrong ACPI GUID is much more serious. Treat this as a cleanup after the GUID fix.

## Finding 10 - The SSDT target plan still makes sense

The SSDT itself is not the first thing I would suspect. The strategy remains logically consistent:

```text
Create ACPI\QCOM0C87 without _DEP
-> allow qcsp.sys to load without SPSS
-> activate PIL TZ interface
-> allow SPSS to finish AddDevice
-> allow original QCSP dependency chain to resolve
```

Given the bad GUID in the EFI injector, the test has likely not yet proven whether the SSDT strategy works or fails. It has only proven that the current injector build is not successfully installing the table.

## Recommended immediate patch

Make this replacement in `build_efi.py`:

```diff
-ACPI_GUID = pack_guid(0x8D59D32B, 0xC655, 0x4AE9,
-                      0x9B, 0x15, 0xF2, 0x59, 0x04, 0x99, 0x2A, 0x43)
+ACPI_GUID = pack_guid(0xffe06bdd, 0x6107, 0x46a6,
+                      0x7b, 0xb2, 0x5a, 0x9c, 0x7e, 0xc5, 0x27, 0x5c)
```

Optional but recommended for the next debug build:

```diff
 blr  x8
+cbnz x0, done_fail
 
 phase2:
```

Optional cleanup:

```diff
-    // LoadImage(TRUE, ImageHandle, NewDevPath, NULL, 0, &win_handle)
+    // LoadImage(FALSE, ImageHandle, NewDevPath, NULL, 0, &win_handle)
     ldr  x8,  [x20, #200]
-    mov  x0,  #1
+    mov  x0,  xzr
```

## Recommended retest sequence

1. Patch `ACPI_GUID`.
2. Rebuild `AcpiInject.efi`.
3. Confirm section flags are still `0xE0000020`.
4. Deploy to:

```powershell
Copy-Item "C:\Drivers\AcpiInject.efi" "D:\EFI\BOOT\BOOTAA64.EFI" -Force
Copy-Item "C:\Drivers\AcpiInject.efi" "D:\EFI\ACPI\AcpiInject.efi" -Force
```

5. Boot from USB via F12.
6. Do not expect GRUB.
7. If Windows boots, run:

```powershell
Get-PnpDevice | Where-Object {$_.InstanceId -like "*QCOM0C87*"} |
    Select-Object FriendlyName, Status, InstanceId

$guid = "{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}"
$base = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$guid"
Get-ChildItem $base -Recurse | Get-ItemProperty |
    Select-Object PSChildName, Linked

Get-PnpDevice | Where-Object {
    $_.InstanceId -like "*QCOM0C1B*" -or
    $_.InstanceId -like "*QCOM0CB0*" -or
    $_.InstanceId -like "*QCOM0C8D*"
} | Select-Object FriendlyName, Status, Problem, InstanceId
```

## How to interpret the next result

### Case A - Windows boots and `QCOM0C87` appears

The EFI table install worked. Continue debugging from Windows/PnP/driver binding.

### Case B - Windows boots but `QCOM0C87` does not appear

The app probably still did not install the SSDT, or Windows ignored the installed table. Build a debug version that prints `LocateProtocol()` and `InstallAcpiTable()` statuses.

### Case C - Firmware immediately returns to boot menu

The app is still crashing or returning an EFI error before chainloading Windows. Build a console debug version. The wrong GUID could have caused this if it resolved to Absolute Pointer and then called a wrong function pointer; after the GUID fix, the failure point should move or disappear.

### Case D - GRUB menu appears

You are not booting the direct `AcpiInject.efi` path. Re-check `D:\EFI\BOOT\BOOTAA64.EFI` size and content.

## Confidence

High confidence:

- The `ACPI_GUID` in the uploaded code is wrong.
- The current GUID corresponds to `EFI_ABSOLUTE_POINTER_PROTOCOL_GUID`.
- The correct `EFI_ACPI_TABLE_PROTOCOL_GUID` is `{FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}`.
- Fixing the GUID is the first required next step.

Medium confidence:

- The bad GUID explains the current no-injection behavior.
- If Absolute Pointer protocol is present, the bad GUID could also explain an immediate firmware return due to a wrong function call.

Lower confidence / not proven yet:

- Whether Windows ARM64 on this exact Acer/Insyde firmware will accept the table once installed correctly.
- Whether the injected `QSP0` device will be enumerated exactly as expected after `InstallAcpiTable()` succeeds.
- Whether the QCSP/SPSS/PIL dependency cascade will fully resolve after `QCOM0C87` appears.

## External references

- UEFI Specification 2.10, ACPI Protocols: https://uefi.org/specs/UEFI/2.10/20_Protocols_ACPI_Protocols.html
- TianoCore/EDK2 Absolute Pointer protocol header showing `{8D59D32B-C655-4AE9-9B15-F25904992A43}` as Absolute Pointer: https://bsdio.com/edk2/docs/master/_absolute_pointer_8h_source.html

## Final verdict

The current build is almost certainly not testing the real ACPI injection path yet, because it is not locating `EFI_ACPI_TABLE_PROTOCOL`. It is locating the wrong GUID. Fix the GUID first, keep the `MEM_WRITE` section flag, then retest without GRUB in the boot path.

---

## Finding 2 — Second wrong-GUID bug: MAP_GUID in Attempts 5l/5m (audit 2026-06-09)

### Code

```python
# build_efi.py lines 106-107 (as written for 5l/5m)
MAP_GUID  = pack_guid(0x6A7A5CFF, 0xE8D9, 0x4F70,
                      0xBA, 0xDA, 0x75, 0xAB, 0x30, 0x25, 0xCE, 0x14)
```

### Why this is wrong

`{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}` is **`EFI_COMPONENT_NAME2_PROTOCOL_GUID`**,
not `EFI_MEMORY_ATTRIBUTE_PROTOCOL`. This is verified against:
- EDK2 `MdePkg/Include/Protocol/MemoryAttribute.h` — correct GUID is
  `{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}`
- `EFI_COMPONENT_NAME2_PROTOCOL` source:
  https://github.com/theopolis/uefi-firmware-parser/blob/master/uefi_firmware/guids/efiguids.py

`EFI_COMPONENT_NAME2_PROTOCOL` is essentially always registered on any UEFI firmware
(used by all standard drivers to expose human-readable names). `LocateProtocol` with
this GUID almost certainly *succeeded* in 5l/5m, and the code then called
`ComponentName2->GetDriverName()` (or similar) at MAP's vtable offsets — invoking an
unrelated function, not `ClearMemoryAttributes()`.

### Consequence

The results of 5l and 5m are invalid, exactly parallel to the 5a–5g ACPI GUID bug:

- 5l's conclusion "MAP absent or also blocked for ACPI memory" is **not supported**.
- 5m's conclusion "DSDT direct-write path confirmed permanently closed" is **not supported**.
- `EFI_MEMORY_ATTRIBUTE_PROTOCOL` has **never been tested** on this firmware.

### Correct fix (applied 2026-06-09)

```python
# EFI_MEMORY_ATTRIBUTE_PROTOCOL_GUID {F4560CF6-40EC-4B4A-A192-BF1D57D0B189} (UEFI 2.10)
MAP_GUID  = pack_guid(0xF4560CF6, 0x40EC, 0x4B4A,
                      0xA1, 0x92, 0xBF, 0x1D, 0x57, 0xD0, 0xB1, 0x89)
```

Fixed in `build_efi.py` as of 2026-06-09. A proper retest (D8) is required:
call `LocateProtocol` for this GUID, print the EFI_STATUS via `ConOut`, and if
found call `GetMemoryAttributes()` then `ClearMemoryAttributes()` on the DSDT
pages, printing each return status explicitly before attempting the byte patch.

"""
Build AcpiInject.efi - AARCH64 UEFI application.

PE format fixes (Session 33):
  - NumDirEntries=16, DllCharacteristics=0x0100 (NX_COMPAT) - required by
    Qualcomm/Insyde UEFI PE loader (GRUB has both; our binary lacked both,
    causing silent LoadImage rejection before entry point was ever called).
  - Proper .reloc section with empty BASE_RELOCATION block.
  - COFF Characteristics 0x020E (matches GRUB).

Session 34 fix: EFI_FILE_PROTOCOL Write=+40, Flush=+80 (was +24/+32 = Delete/Read).

Session 35 fix: Replace LoadedImage-based log setup with brute-force SFS scan.
Session 36 fix: Removed marker file check from log setup loop.
Session 37 fix: Replaced EFI_ACPI_TABLE_PROTOCOL with UEFI SetVariable logging
  (both dead on this Insyde platform - protocol not found, variables unreadable).

Session 38 Phase 1 rewrite: Direct XSDT modification.
  EFI_ACPI_TABLE_PROTOCOL is not present or rejected on this Insyde H2O firmware.
  UEFI runtime variable services (GetFirmwareEnvironmentVariableW) are also blocked
  at the kernel level for all variables including BootOrder - confirmed error 1314
  even in elevated context with SeSystemEnvironmentPrivilege present.

Session 39 (Attempt 5i): Direct XSDT append in EfiACPIMemoryNVS.
  RSDP->XsdtAddress write silently ignored - RSDP is in write-protected EFI memory.

Session 40 (Attempt 5k): DSDT in-place _DEP patch.
  DSDT[0x36C69] write also silently ignored - DSDT is also in write-protected EFI memory.
  Entire ACPI table chain (RSDP, XSDT, FADT, DSDT) is in firmware-managed read-only pages.
  Writes don't fault (no boot menu) but don't take effect either.

Session 40 (Attempt 5l): EFI_MEMORY_ATTRIBUTE_PROTOCOL unprotect before DSDT patch.
  Before writing to DSDT, call ClearMemoryAttributes() to lift the read-only attribute
  on the DSDT page(s). GUID: {6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14} (UEFI 2.10).
  *** AUDIT NOTE (2026-06-09): that GUID is EFI_COMPONENT_NAME2_PROTOCOL, not MAP.
  *** LocateProtocol most likely succeeded against the wrong protocol and called its
  *** vtable at MAP offsets. 5l/5m results are INVALID -- MAP was never tested.
  *** Correct GUID is {F4560CF6-40EC-4B4A-A192-BF1D57D0B189}; fixed above at MAP_GUID.
  If protocol absent: fall through to DSDT write anyway, then chainload.
  Success check: HKLM\\HARDWARE\\ACPI\\DSDT\\...\\00000000 bytes at 0x36C69 == 47 4C 4E 4B (GLNK).

Session 46-47 (Attempt 5m): MAP canary write + 3-second stall for visual confirmation.
  Canary: write 0x41414141 to DSDT[0x20] (CreatorRevision, safe metadata, never read
    by ACPI interpreter; pre-write value 0x05000000).
  Stall placed at phase2 entry (was dead code in loop tail in 5l).
  Result (Session 47): canary UNCHANGED (00 00 00 05). INVALID -- wrong GUID used (see
  5l note above). This result does NOT establish MAP absent or ClearMemoryAttributes
  non-functional; those conclusions must be re-derived with the correct GUID (D8).

Session 53 (Attempt D8): EFI_MEMORY_ATTRIBUTE_PROTOCOL retest with correct GUID.
  Replaces Phase 1 entirely with D8 logic:
    1. Navigate ConfigurationTable -> RSDP -> XSDT -> FADT -> DSDT physical address.
    2. LocateProtocol(MAP_GUID) -- print 16-hex status; if EFI_NOT_FOUND, skip to chainload.
    3. GetMemoryAttributes(DSDT_phys, 0x1000) -- print GA status + attrs bits.
    4. ClearMemoryAttributes(page-aligned DSDT base, 0x50000, EFI_MEMORY_RO=0x20000).
       EFI_MEMORY_RO = BIT17 = 0x20000 (UEFI 2.10 Table 2-4). Prior handoff doc had 0x4000
       which is EFI_MEMORY_XP (execute-protect), not read-only. Corrected here.
    5. Canary write 0x47 to DSDT[0x36C69], read back -- print CW=<byte>.
    6. If canary byte == 0x47: write full GLNK patch (4C 4E 4B) + fix checksum 0x78->0x95.
  All EFI_STATUS values printed as 16 hex digits on ConOut via d8_print_hex64 subroutine.
  d8_print_hex64: saves/restores lr; uses static d8_hex_buf (40 bytes); UTF-16 output.

Session 47 (Attempt 5n): BootServices->InstallConfigurationTable() approach.
  All DSDT/RSDP direct-write paths exhausted (firmware-managed read-only pages).
  New approach: call firmware's own InstallConfigurationTable() to replace the ACPI
  2.0 GUID entry in SystemTable->ConfigurationTable[] with a pointer to a new NVS
  RSDP+XSDT+SSDT chain -- never writes to firmware-owned memory directly.
  Algorithm:
    1. Walk ConfigurationTable -> find ACPI 2.0 GUID entry -> read old RSDP (read-only)
    2. AllocatePages(EfiACPIMemoryNVS, 4 pages): new_rsdp (+0x0000), new_xsdt (+0x1000),
       new_ssdt (+0x3000)
    3. Copy old RSDP to new_rsdp; update new_rsdp->XsdtAddress to new_xsdt
    4. Copy old XSDT to new_xsdt; append new_ssdt ptr; update Length; recalculate checksum
    5. Copy 80-byte SSDT stub to new_ssdt
    6. Recalculate new_rsdp extended checksum (byte +32, covers bytes 0-35)
    7. InstallConfigurationTable(&ACPI_20_GUID, new_rsdp) -- replaces firmware entry
    8. Chainload Windows (Phase 2 unchanged)
  BootServices offsets: AllocatePages=+0x028 (40), InstallConfigurationTable=+0x0C0 (192).
  Success check: HKLM\\HARDWARE\\ACPI\\SSDT should gain a QCOMM_ key; QCOM0C87 in PnP.

ADD_STALL: if True, inserts a 3-second Stall between Phase 1 and Phase 2.
  Use to confirm binary is executing - boot takes 3 extra seconds if running.
  Set False for normal use.

Execution sequence:
  1. Prologue + setup BootServices / ConOut
  2. Log file setup: LocateHandleBuffer(SFS) -> try Open/create \\ai_debug.txt
  3. ConOut "[AI] start"
  4. Phase 1: MAP unprotect + DSDT in-place _DEP patch
  5. (optional) 3s Stall
  6. Phase 2: walk SFS handles, find bootmgfw.efi, LoadImage + StartImage

Toggle SKIP_ACPI=True to bypass Phase 1 (test chainload only).
Toggle ADD_STALL=True to add 3s delay confirming binary execution.
"""

import struct
import sys
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN

SKIP_ACPI = False   # True = jump straight to Phase 2
ADD_STALL = True    # True = 3-second stall at phase2 entry (confirms binary executed to chainload point)

with open(r"C:\Drivers\ssdt_qcsp.aml", "rb") as f:
    ssdt_bytes = f.read()
assert len(ssdt_bytes) == 80

def pack_guid(a, b, c, *d):
    return struct.pack("<IHH8B", a, b, c, *d)

# EFI_ACPI_TABLE_PROTOCOL_GUID  {FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}
ACPI_GUID = pack_guid(0xffe06bdd, 0x6107, 0x46a6,
                      0x7b, 0xb2, 0x5a, 0x9c, 0x7e, 0xc5, 0x27, 0x5c)
# EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID
SFS_GUID  = pack_guid(0x964E5B22, 0x6459, 0x11D2,
                      0x8E, 0x39, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B)
# EFI_DEVICE_PATH_PROTOCOL_GUID
DP_GUID   = pack_guid(0x09576E91, 0x6D3F, 0x11D2,
                      0x8E, 0x39, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B)
# Vendor GUID for AcpiLog UEFI variable  {DEADBEEF-CAFE-1234-ABCD-000000000042}
VAR_GUID  = pack_guid(0xDEADBEEF, 0xCAFE, 0x1234,
                      0xAB, 0xCD, 0x00, 0x00, 0x00, 0x00, 0x00, 0x42)
# EFI_MEMORY_ATTRIBUTE_PROTOCOL_GUID {F4560CF6-40EC-4B4A-A192-BF1D57D0B189} (UEFI 2.10)
# EDK2 MdePkg/Include/Protocol/MemoryAttribute.h -- verified 2026-06-09.
# Prior value {6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14} was EFI_COMPONENT_NAME2_PROTOCOL
# (essentially always present) -- 5l/5m never invoked MAP; see FINDINGS.md §8 audit note.
MAP_GUID  = pack_guid(0xF4560CF6, 0x40EC, 0x4B4A,
                      0xA1, 0x92, 0xBF, 0x1D, 0x57, 0xD0, 0xB1, 0x89)
# EFI_LOADED_IMAGE_PROTOCOL_GUID - no longer used (log setup uses SFS scan instead)

log_path_utf16     = "\\ai_debug.txt".encode("utf-16-le") + b"\x00\x00"   # 28 bytes
var_name_utf16     = "AcpiLog".encode("utf-16-le") + b"\x00\x00"          # 16 bytes
ssdt_aml_path_utf16 = r"\ssdt_qcsp.aml".encode("utf-16-le") + b"\x00\x00"  # 30 bytes
bootmgfw_utf16     = r"\EFI\Microsoft\Boot\bootmgfw.efi".encode("utf-16-le") + b"\x00\x00"
assert len(bootmgfw_utf16) == 66

def u16(s):
    return s.encode("utf-16-le") + b"\x00\x00"

def b2a(b):
    return ", ".join(f"0x{x:02x}" for x in b)

def a2a(s):
    return ", ".join(f"0x{ord(c):02x}" for c in s)

# ConOut UTF-16 strings
cstr_start      = u16("[AI] start\r\n")
cstr_acpi_loc   = u16("[AI] Locate ACPI\r\n")
cstr_acpi_ok    = u16("[AI] ACPI proto ok\r\n")
cstr_acpi_fail  = u16("[AI] ACPI proto fail\r\n")
cstr_ssdt_call  = u16("[AI] InstallAcpiTable\r\n")
cstr_ssdt_ok    = u16("[AI] SSDT ok\r\n")
cstr_ssdt_fail  = u16("[AI] SSDT fail\r\n")
cstr_sfs_scan   = u16("[AI] SFS scan\r\n")
cstr_sfs_fail   = u16("[AI] SFS fail\r\n")
cstr_found      = u16("[AI] bootmgfw found\r\n")
cstr_load_call  = u16("[AI] LoadImage\r\n")
cstr_load_ok    = u16("[AI] LoadImage ok\r\n")
cstr_load_fail  = u16("[AI] LoadImage fail\r\n")
cstr_start_img  = u16("[AI] StartImage\r\n")
cstr_canary     = u16("[AI] canary write\r\n")
cstr_ict_ok     = u16("[AI] ICT=OK\r\n")
cstr_ict_err    = u16("[AI] ICT=ERR\r\n")
cstr_ct_ours    = u16("[AI] CT=OURS\r\n")
cstr_ct_old     = u16("[AI] CT=OLD\r\n")
cstr_ct_gone    = u16("[AI] CT=NONE\r\n")

# D8 ConOut strings
cstr_d8_start    = u16("[D8] START\r\n")
cstr_d8_dsdt     = u16("[D8] DSDT=\r\n")
cstr_d8_map_lp   = u16("[D8] MAP LP=\r\n")
cstr_d8_map_nf   = u16("[D8] MAP NF\r\n")
cstr_d8_ga       = u16("[D8] GA=\r\n")
cstr_d8_a        = u16("[D8] A=\r\n")
cstr_d8_ca       = u16("[D8] CA=\r\n")
cstr_d8_cw       = u16("[D8] CW=\r\n")
cstr_d8_patch_ok = u16("[D8] PATCH=OK\r\n")
cstr_d8_no_dsdt  = u16("[D8] NO DSDT\r\n")

# Log file ASCII strings
LOG_STRS = {
    "entry":    "[AI] ENTRY\r\n",    # written immediately after log file opens
    "start":    "[AI] start\r\n",
    "log_open": "[AI] log open\r\n",
    "log_fail": "[AI] log open failed\r\n",
    "acpi_loc": "[AI] Locate ACPI\r\n",
    "acpi_ok":  "[AI] ACPI proto ok\r\n",
    "acpi_fail":"[AI] ACPI proto fail\r\n",
    "ssdt_call":"[AI] InstallAcpiTable\r\n",
    "ssdt_ok":  "[AI] SSDT ok\r\n",
    "ssdt_fail":"[AI] SSDT fail\r\n",
    "sfs_scan": "[AI] SFS scan\r\n",
    "sfs_fail": "[AI] SFS fail\r\n",
    "found":    "[AI] bootmgfw found\r\n",
    "load_call":"[AI] LoadImage\r\n",
    "load_ok":  "[AI] LoadImage ok\r\n",
    "load_fail":"[AI] LoadImage fail\r\n",
    "start_img":"[AI] StartImage\r\n",
    "done_fail":"[AI] DONE FAIL\r\n",
}

# EFI_SYSTEM_TABLE offsets (64-bit pointers):
#   +64  (0x040): ConOut
#   +96  (0x060): BootServices
#
# EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL: OutputString at +8
#
# EFI_BOOT_SERVICES offsets:
#   +40  (0x028): AllocatePages        (NEW in 5n)
#   +64  (0x040): AllocatePool
#   +152 (0x098): HandleProtocol
#   +192 (0x0C0): InstallConfigurationTable  (NEW in 5n)
#   +200 (0x0C8): LoadImage
#   +208 (0x0D0): StartImage
#   +232 (0x0E8): ExitBootServices
#   +248 (0x0F8): Stall
#   +312 (0x138): LocateHandleBuffer
#   +320 (0x140): LocateProtocol
#   +352 (0x160): CopyMem
#
# EFI_SIMPLE_FILE_SYSTEM_PROTOCOL: OpenVolume at +8
# EFI_FILE_PROTOCOL: Revision +0, Open +8, Close +16, Delete +24, Read +32,
#   Write +40, GetPosition +48, SetPosition +56, GetInfo +64, SetInfo +72, Flush +80
#
# Register allocation (callee-saved x19-x28):
#   x19 = ImageHandle
#   x20 = BootServices
#   x21 = SFS loop index i (reused in log setup and Phase 2)
#   x22 = SFS HandleCount  (reused in log setup and Phase 2)
#   x23 = SFS HandleBuffer ptr (reused in log setup and Phase 2)
#   x24 = scratch (Open status / BaseDevPathLen)
#   x25 = scratch (current SFS handle / BaseDevPath ptr)
#   x26 = ConOut ptr
#   x27 = SystemTable ptr
#   x28 = log file handle (EFI_FILE_PROTOCOL*), 0 = not open

_wl_counters = {}

def print_asm(cstr_label):
    """Inline ConOut->OutputString. Clobbers x0, x1, x8."""
    return f"""
    mov  x0,  x26
    adr  x1,  {cstr_label}
    ldr  x8,  [x26, #8]
    blr  x8
"""

def write_log(key):
    """
    Inline EFI_FILE_PROTOCOL->Write + Flush for log entry.
    x28 = log file handle (skipped if 0).
    Clobbers x0, x1, x8, x9.
    """
    _wl_counters[key] = _wl_counters.get(key, 0) + 1
    uid = _wl_counters[key]
    size = len(LOG_STRS[key])
    return f"""
    cbz  x28, wl_skip_{key}_{uid}
    adr  x1,  log_write_size
    mov  x9,  #{size}
    str  x9,  [x1]
    mov  x0,  x28
    ldr  x8,  [x28, #40]        // EFI_FILE_PROTOCOL->Write (+40)
    adr  x2,  lstr_{key}
    blr  x8
    mov  x0,  x28
    ldr  x8,  [x28, #80]        // EFI_FILE_PROTOCOL->Flush (+80)
    blr  x8
wl_skip_{key}_{uid}:
"""

def debug(key, cstr_label):
    """ConOut print + log write."""
    return print_asm(cstr_label) + write_log(key)

# set_var: write a 1-byte status to UEFI NVRAM variable "AcpiLog".
# No filesystem dependency - uses RuntimeServices->SetVariable directly.
# Status chars: 'A'=ACPI proto not found, '1'=InstallAcpiTable failed, '2'=SSDT ok.
# Read from Windows after boot with GetFirmwareEnvironmentVariableW (see Session 37 notes).
_sv_counters = {}
def set_var(status_char):
    _sv_counters[status_char] = _sv_counters.get(status_char, 0) + 1
    uid = _sv_counters[status_char]
    return f"""
    ldr  x8,  [x27, #88]       // SystemTable->RuntimeServices
    ldr  x9,  [x8,  #88]       // RuntimeServices->SetVariable
    adr  x0,  var_name_utf16
    adr  x1,  var_guid
    mov  x2,  #7               // NV|BS|RT
    mov  x3,  #1               // DataSize=1
    adr  x4,  sv_data_{status_char}_{uid}
    blr  x9
    b    sv_done_{status_char}_{uid}
sv_data_{status_char}_{uid}:
    .byte 0x{ord(status_char):02x}
    .balign 8
sv_done_{status_char}_{uid}:
"""

# -- Phase 1 assembly ---------------------------------------------------
# Session 38: Direct XSDT modification.
# SystemTable offsets (64-bit): ConOut=+64, RuntimeSvc=+88, BootSvc=+96,
#   NumberOfTableEntries=+104, ConfigurationTable=+112.
# EFI_CONFIGURATION_TABLE: GUID(16 bytes) + VendorTable ptr(8 bytes) = 24 bytes/entry.
# RSDP (ACPI 2.0): XsdtAddress at +24 (UINT64), ExtendedChecksum at +32 (covers 36B).
# XSDT: Length at +4 (UINT32), Checksum at +9 (UINT8), entries from +36 (8B each).
# EFI_ACPI_20_TABLE_GUID = {8868E871-E4F1-11D3-BC22-0080C73C8881}
#   packed bytes: 71 E8 68 88 F1 E4 D3 11 BC 22 00 80 C7 3C 88 81
#   as uint64 LE: lo=0x11D3E4F18868E871  hi=0x81883CC7800022BC
# BootServices offsets: AllocatePages=+40, AllocatePool=+64, CopyMem=+352.
stall_asm = ""
if ADD_STALL:
    # 8-second stall (8,000,000 microseconds = 0x7A1200)
    # BootServices->Stall is at offset +0xF8 = 248
    # NOTE: prior builds incorrectly used offset 232 (0xE8) = ExitBootServices, not Stall.
    #       ExitBootServices with invalid args returns EFI_INVALID_PARAMETER immediately.
    #       This is now fixed; offset 248 (0xF8) is the correct Stall function.
    stall_asm = """
    // 8-second stall (ADD_STALL=True) - hold screen so user can read ICT diagnostic output
    ldr  x8,  [x20, #248]       // BootServices->Stall (+0xF8) -- fixed from 232 which is ExitBootServices
    movz x0,  #0x1200
    movk x0,  #0x007A, lsl #16  // 8000000 = 0x7A1200
    blr  x8
"""

if SKIP_ACPI:
    phase1_asm = "    b    phase2    // SKIP_ACPI=True\n"
else:
    phase1_asm = f"""
    // Phase 1: D8 -- EFI_MEMORY_ATTRIBUTE_PROTOCOL DSDT unprotect + in-place patch
    // First valid MAP test: correct GUID {{F4560CF6-40EC-4B4A-A192-BF1D57D0B189}}.
    // Prior 5l/5m used EFI_COMPONENT_NAME2_PROTOCOL GUID -- MAP was never invoked.
    //
    // Steps:
    //   1. Navigate ConfigurationTable -> RSDP -> XSDT -> FADT (X_DSDT) -> DSDT phys addr
    //   2. LocateProtocol(MAP_GUID) -- EFI_NOT_FOUND -> skip to phase2
    //   3. GetMemoryAttributes(DSDT_phys, 1 page) -- print GA status + attrs bits
    //   4. ClearMemoryAttributes(page-base, 0x50000, EFI_MEMORY_RO=0x20000) -- BIT17
    //   5. Canary: write 0x47 at DSDT[0x36C69], read back
    //   6. If canary == 0x47: write GLNK patch + fix checksum DSDT[9]=0x95
{print_asm("cstr_d8_start")}

    // Step 1: walk ConfigurationTable for ACPI 2.0 GUID
    ldr  x22, [x27, #104]       // NumberOfTableEntries (callee-saved)
    ldr  x23, [x27, #112]       // ConfigurationTable ptr (callee-saved)
    mov  x21, xzr               // loop index (callee-saved)

d8_cfg_loop:
    cmp  x21, x22
    bge  d8_no_dsdt

    mov  x8,  #24
    mul  x8,  x21, x8
    add  x8,  x23, x8           // &ConfigurationTable[i]

    ldr  x0,  [x8]
    ldr  x1,  acpi20_guid_lo
    cmp  x0,  x1
    bne  d8_cfg_next

    ldr  x0,  [x8, #8]
    ldr  x1,  acpi20_guid_hi
    cmp  x0,  x1
    bne  d8_cfg_next

    ldr  x24, [x8, #16]         // x24 = RSDP address (callee-saved)
    b    d8_found_rsdp

d8_cfg_next:
    add  x21, x21, #1
    b    d8_cfg_loop

d8_found_rsdp:
    ldr  x21, [x24, #24]        // x21 = XSDT address (callee-saved)
    ldr  w22, [x21, #4]         // XSDT Length (UINT32)
    uxtw x22, w22               // x22 = XSDT Length zero-extended (callee-saved)
    mov  x23, #36               // x23 = entry byte offset; entries start at +36 (callee-saved)

d8_xsdt_loop:
    cmp  x23, x22
    bge  d8_no_dsdt

    ldr  x8,  [x21, x23]        // table entry physical address
    ldr  w0,  [x8]              // 4-byte signature
    movz w9,  #0x4146
    movk w9,  #0x5043, lsl #16  // 0x50434146 = "FACP" little-endian
    cmp  w0,  w9
    beq  d8_found_fadt
    add  x23, x23, #8
    b    d8_xsdt_loop

d8_found_fadt:
    // x8 = FADT physical address; X_DSDT (UINT64) at FADT+0x8C (ACPI spec)
    ldr  x25, [x8, #0x8C]       // x25 = DSDT physical address (callee-saved)
{print_asm("cstr_d8_dsdt")}
    mov  x0,  x25
    bl   d8_print_hex64

    // Step 2: LocateProtocol(MAP_GUID)
    ldr  x8,  [x20, #320]       // BootServices->LocateProtocol (+0x140)
    adr  x0,  map_proto_guid
    mov  x1,  xzr
    adr  x2,  map_proto_ptr
    blr  x8
    mov  x24, x0                // x24 = LocateProtocol status (callee-saved)
{print_asm("cstr_d8_map_lp")}
    mov  x0,  x24
    bl   d8_print_hex64
    cbnz x24, d8_map_not_found  // non-zero = not found / error

    ldr  x24, map_proto_ptr     // x24 = MAP interface pointer (callee-saved)

    // Step 3: GetMemoryAttributes(MAP, DSDT_phys, 0x1000, &d8_attrs)
    // MAP vtable: [+0]=GetMemoryAttributes [+8]=SetMemoryAttributes [+16]=ClearMemoryAttributes
    mov  x0,  x24               // This
    mov  x1,  x25               // BaseAddress = DSDT physical
    mov  x2,  #0x1000           // Length = 1 page (diagnostic probe)
    adr  x3,  d8_attrs          // Attributes out-param
    ldr  x8,  [x24, #0]         // MAP->GetMemoryAttributes
    blr  x8
    mov  x22, x0                // x22 = GA status (callee-saved)
{print_asm("cstr_d8_ga")}
    mov  x0,  x22
    bl   d8_print_hex64
{print_asm("cstr_d8_a")}
    ldr  x0,  d8_attrs
    bl   d8_print_hex64

    // Step 4: ClearMemoryAttributes(MAP, page-aligned DSDT base, 0x50000, EFI_MEMORY_RO)
    // EFI_MEMORY_RO = 0x20000 = BIT17 (UEFI 2.10 Table 2-4; note: NOT 0x4000=EFI_MEMORY_XP)
    mov  x0,  x24               // This
    and  x1,  x25, #~0xFFF      // page-align DSDT physical address
    mov  x2,  #0x50000          // 320KB span covers full 279KB DSDT
    mov  x3,  #0x20000          // EFI_MEMORY_RO
    ldr  x8,  [x24, #16]        // MAP->ClearMemoryAttributes
    blr  x8
    mov  x22, x0                // x22 = CA status (callee-saved)
{print_asm("cstr_d8_ca")}
    mov  x0,  x22
    bl   d8_print_hex64

    // Step 5: Canary write -- 0x47 ('G') to DSDT[0x36C69], read back
    // 0x36C69 = 0x3_6C69
    movz x8,  #0x6C69
    movk x8,  #0x3, lsl #16     // x8 = 0x36C69 = offset of patch byte in DSDT
    add  x21, x25, x8           // x21 = &DSDT[0x36C69] (callee-saved, survives bl)
    mov  w0,  #0x47
    strb w0,  [x21]
    ldrb w22, [x21]             // x22 = readback byte (callee-saved, survives bl)
{print_asm("cstr_d8_cw")}
    uxtb x0,  w22
    bl   d8_print_hex64

    // Step 6: apply full patch only if canary confirms write took effect
    cmp  w22, #0x47
    bne  phase2                 // write silently dropped -- exit gracefully

    // GLNK patch: DSDT[0x36C69..0x36C6C] = 47 4C 4E 4B ("GLNK")
    // First byte already written (canary). Write remaining three.
    mov  w0,  #0x4C             // 'L'
    strb w0,  [x21, #1]
    mov  w0,  #0x4E             // 'N'
    strb w0,  [x21, #2]
    mov  w0,  #0x4B             // 'K'
    strb w0,  [x21, #3]
    // Checksum fix: DSDT[9] 0x78 -> 0x95 (GLNK byte-sum=300 vs SPSS byte-sum=329, delta=-29=0x1D)
    mov  w0,  #0x95
    strb w0,  [x25, #9]
{print_asm("cstr_d8_patch_ok")}
    b    phase2

d8_map_not_found:
{print_asm("cstr_d8_map_nf")}
    b    phase2

d8_no_dsdt:
{print_asm("cstr_d8_no_dsdt")}
    b    phase2

// Subroutine d8_print_hex64
// Input: x0 = 64-bit value to print as 16 uppercase hex chars + CRLF on ConOut
// x26 must hold ConOut ptr (not clobbered by this routine)
// Saves/restores lr. Clobbers x0-x3, x8, x9.
d8_print_hex64:
    str  lr,  [sp, #-16]!
    mov  x3,  x0                // working copy of value (x3 caller-saved, ok in loop)
    adr  x9,  d8_hex_buf        // write ptr into static UTF-16 output buffer
    mov  x2,  #16               // 16 nibbles
d8_hex_loop:
    lsr  x0,  x3, #60           // extract MSB nibble
    and  x0,  x0, #0xF
    lsl  x3,  x3, #4            // advance to next nibble
    cmp  x0,  #10
    bge  d8_hex_alpha
    add  x0,  x0, #0x30         // ASCII '0'-'9'
    b    d8_hex_store
d8_hex_alpha:
    add  x0,  x0, #0x37         // ASCII 'A'=0x41 (10+0x37=0x41)
d8_hex_store:
    strh w0,  [x9], #2          // store UTF-16 char (ASCII BMP, zero-extends), advance ptr
    subs x2,  x2, #1
    bne  d8_hex_loop
    mov  x0,  #0x0D
    strh w0,  [x9], #2
    mov  x0,  #0x0A
    strh w0,  [x9], #2
    strh wzr, [x9]              // null-terminate
    mov  x0,  x26
    adr  x1,  d8_hex_buf
    ldr  x8,  [x26, #8]         // ConOut->OutputString
    blr  x8
    ldr  lr,  [sp], #16
    ret
"""

# (old 5n InstallConfigurationTable code removed; see git history for attempt 5n/5o)

# -- Main assembly ------------------------------------------------------
ASM = f"""
    // Prologue: save x19-x28 + lr = 11 regs, 96-byte frame
    stp  x19, x20, [sp, #-96]!
    stp  x21, x22, [sp, #16]
    stp  x23, x24, [sp, #32]
    stp  x25, x26, [sp, #48]
    stp  x27, x28, [sp, #64]
    str  lr,       [sp, #80]

    mov  x19, x0               // ImageHandle
    mov  x27, x1               // SystemTable
    ldr  x20, [x27, #96]       // BootServices
    ldr  x26, [x27, #64]       // ConOut
    mov  x28, xzr              // log file not open yet

    // ---- Log file setup: try each SFS handle (Session 36) ----
    // USB SFS handle is NOT in LocateHandleBuffer list on this Insyde firmware -
    // only NVMe SFS handles are globally registered.  Removed marker file check;
    // now just try to create \\ai_debug.txt on the first writable SFS volume.
    // Expected: NVMe EFI partition (FAT32).  After boot, check S:\\ (mountvol S: /s).

    ldr  x8,  [x20, #312]      // BootServices->LocateHandleBuffer
    mov  x0,  #2               // SearchType=ByProtocol
    adr  x1,  sfs_guid
    mov  x2,  xzr
    adr  x3,  log_hcount
    adr  x4,  log_hbuf
    blr  x8
    cbnz x0,  log_setup_done   // no SFS handles at all

    ldr  x22, log_hcount
    ldr  x23, log_hbuf
    mov  x21, xzr              // i = 0

log_sfs_loop:
    cmp  x21, x22
    bge  log_setup_done        // all handles exhausted

    lsl  x9,  x21, #3
    ldr  x25, [x23, x9]       // handle = HandleBuffer[i]

    ldr  x8,  [x20, #152]     // HandleProtocol
    mov  x0,  x25
    adr  x1,  sfs_guid
    adr  x2,  log_sfs_ptr
    blr  x8
    cbnz x0,  log_next

    ldr  x0,  log_sfs_ptr
    ldr  x8,  [x0, #8]        // SFS->OpenVolume
    adr  x1,  log_root_ptr
    blr  x8
    cbnz x0,  log_next

    // Try to Open/create \\ai_debug.txt on this volume
    ldr  x0,  log_root_ptr
    ldr  x8,  [x0, #8]        // EFI_FILE_PROTOCOL->Open
    adr  x1,  log_file_ptr
    adr  x2,  log_path_utf16
    mov  x3,  #3
    movk x3,  #0x8000, lsl #48
    mov  x4,  #0x20
    blr  x8
    mov  x24, x0               // save Open status

    // Close root regardless of whether Open succeeded
    ldr  x0,  log_root_ptr
    ldr  x8,  [x0, #16]       // Close root
    blr  x8

    cbnz x24, log_next         // Open failed on this volume, try next

    ldr  x28, log_file_ptr     // x28 = log file handle (non-zero = success)
{write_log("entry")}
{write_log("log_open")}
    b    log_setup_done

log_next:
    add  x21, x21, #1
    b    log_sfs_loop

log_setup_done:
    // ---- ConOut print "[AI] start" ----
{print_asm("cstr_start")}
{write_log("start")}

    // ---- Phase 1 ----
{phase1_asm}

phase2:
    // Phase 2: scan SFS handles for bootmgfw.efi
{stall_asm}
{debug("sfs_scan", "cstr_sfs_scan")}
    ldr  x8,  [x20, #312]      // LocateHandleBuffer
    mov  x0,  #2               // ByProtocol
    adr  x1,  sfs_guid
    mov  x2,  xzr
    adr  x3,  handle_count
    adr  x4,  handle_buffer_ptr
    blr  x8
    cbz  x0,  sfs_handles_ok
{debug("sfs_fail", "cstr_sfs_fail")}
    b    done_fail

sfs_handles_ok:
    ldr  x22, handle_count
    ldr  x23, handle_buffer_ptr
    mov  x21, xzr

loop_start:
    cmp  x21, x22
    bge  all_handles_done

    lsl  x0,  x21, #3
    ldr  x25, [x23, x0]        // HandleBuffer[i]

    ldr  x8,  [x20, #152]
    mov  x0,  x25
    adr  x1,  sfs_guid
    adr  x2,  sfs_ptr
    blr  x8
    cbnz x0,  next_handle

    ldr  x0,  sfs_ptr
    ldr  x8,  [x0, #8]
    adr  x1,  root_ptr
    blr  x8
    cbnz x0,  next_handle

    ldr  x0,  root_ptr
    ldr  x8,  [x0, #8]
    adr  x1,  file_ptr
    adr  x2,  bootmgfw_utf16
    mov  x3,  #1
    mov  x4,  xzr
    blr  x8
    mov  x24, x0

    ldr  x0,  root_ptr
    ldr  x9,  [x0, #16]
    blr  x9

    cbnz x24, next_handle

    // Found bootmgfw.efi - close the file handle (existence check done)
    ldr  x0,  file_ptr
    ldr  x8,  [x0, #16]
    blr  x8

{debug("found", "cstr_found")}

    // Get device path for this handle
    ldr  x8,  [x20, #152]
    mov  x0,  x25
    adr  x1,  dp_guid
    adr  x2,  devpath_ptr
    blr  x8
    cbnz x0,  next_handle

    // Walk device path to measure base length (up to END node)
    ldr  x25, devpath_ptr
    mov  x24, xzr

walk_loop:
    add  x9,  x25, x24
    ldrb w0,  [x9, #0]
    ldrb w1,  [x9, #1]
    cmp  w0,  #0x7F
    bne  walk_not_end
    cmp  w1,  #0xFF
    beq  walk_done
walk_not_end:
    ldrh w0,  [x9, #2]
    add  x24, x24, x0
    b    walk_loop

walk_done:
    // Allocate: BaseLen + FILEPATH header(4) + path(66) + END(4) = BaseLen+74
    ldr  x8,  [x20, #64]       // AllocatePool
    mov  x0,  #2               // EfiLoaderData
    add  x1,  x24, #74
    adr  x2,  new_devpath_ptr
    blr  x8
    cbnz x0,  done_fail

    // CopyMem(NewDevPath, BaseDevPath, BaseLen)
    ldr  x0,  new_devpath_ptr
    mov  x1,  x25
    mov  x2,  x24
    ldr  x8,  [x20, #352]
    blr  x8

    // Append FILEPATH node: Type=4, SubType=4, Length=70
    ldr  x9,  new_devpath_ptr
    add  x9,  x9,  x24
    mov  w0,  #4
    strb w0,  [x9, #0]
    strb w0,  [x9, #1]
    mov  w0,  #70
    strb w0,  [x9, #2]
    mov  w0,  #0
    strb w0,  [x9, #3]

    // CopyMem(node+4, bootmgfw_utf16, 66)
    add  x0,  x9,  #4
    adr  x1,  bootmgfw_utf16
    mov  x2,  #66
    ldr  x8,  [x20, #352]
    blr  x8

    // Append END node: 0x7F 0xFF 0x04 0x00
    ldr  x9,  new_devpath_ptr
    add  x9,  x9,  x24
    add  x9,  x9,  #70
    mov  w0,  #0x7F
    strb w0,  [x9, #0]
    mov  w0,  #0xFF
    strb w0,  [x9, #1]
    mov  w0,  #4
    strb w0,  [x9, #2]
    mov  w0,  #0
    strb w0,  [x9, #3]

    // LoadImage(BootPolicy=FALSE, ImageHandle, NewDevPath, NULL, 0, &win_handle)
{debug("load_call", "cstr_load_call")}
    ldr  x8,  [x20, #200]
    mov  x0,  xzr
    mov  x1,  x19
    ldr  x2,  new_devpath_ptr
    mov  x3,  xzr
    mov  x4,  xzr
    adr  x5,  win_handle
    blr  x8
    cbz  x0,  load_image_ok
{debug("load_fail", "cstr_load_fail")}
    b    done_fail

load_image_ok:
{debug("load_ok", "cstr_load_ok")}
{debug("start_img", "cstr_start_img")}
    // Close log before StartImage (Windows loader calls ExitBootServices)
    cbz  x28, log_pre_start_done
    mov  x0,  x28
    ldr  x8,  [x28, #16]
    blr  x8
    mov  x28, xzr
log_pre_start_done:
    ldr  x8,  [x20, #208]      // StartImage
    ldr  x0,  win_handle
    mov  x1,  xzr
    mov  x2,  xzr
    blr  x8
    b    done_ok

next_handle:
    add  x21, x21, #1
    b    loop_start

all_handles_done:
{debug("sfs_fail", "cstr_sfs_fail")}

done_fail:
{write_log("done_fail")}
    cbz  x28, df_log_closed
    mov  x0,  x28
    ldr  x8,  [x28, #16]
    blr  x8
    mov  x28, xzr
df_log_closed:
    mov  x0,  xzr
    movk x0,  #0x8000, lsl #48
    orr  x0,  x0,  #3          // EFI_UNSUPPORTED

done_ok:
    // Epilogue
    ldr  lr,       [sp, #80]
    ldp  x27, x28, [sp, #64]
    ldp  x25, x26, [sp, #48]
    ldp  x23, x24, [sp, #32]
    ldp  x21, x22, [sp, #16]
    ldp  x19, x20, [sp], #96
    ret

    .balign 8
cstr_start:
    .byte {b2a(cstr_start)}
    .balign 8
cstr_acpi_loc:
    .byte {b2a(cstr_acpi_loc)}
    .balign 8
cstr_acpi_ok:
    .byte {b2a(cstr_acpi_ok)}
    .balign 8
cstr_acpi_fail:
    .byte {b2a(cstr_acpi_fail)}
    .balign 8
cstr_ssdt_call:
    .byte {b2a(cstr_ssdt_call)}
    .balign 8
cstr_ssdt_ok:
    .byte {b2a(cstr_ssdt_ok)}
    .balign 8
cstr_ssdt_fail:
    .byte {b2a(cstr_ssdt_fail)}
    .balign 8
cstr_sfs_scan:
    .byte {b2a(cstr_sfs_scan)}
    .balign 8
cstr_sfs_fail:
    .byte {b2a(cstr_sfs_fail)}
    .balign 8
cstr_found:
    .byte {b2a(cstr_found)}
    .balign 8
cstr_load_call:
    .byte {b2a(cstr_load_call)}
    .balign 8
cstr_load_ok:
    .byte {b2a(cstr_load_ok)}
    .balign 8
cstr_load_fail:
    .byte {b2a(cstr_load_fail)}
    .balign 8
cstr_start_img:
    .byte {b2a(cstr_start_img)}
    .balign 8
cstr_canary:
    .byte {b2a(cstr_canary)}
    .balign 8
cstr_ict_ok:
    .byte {b2a(cstr_ict_ok)}
    .balign 8
cstr_ict_err:
    .byte {b2a(cstr_ict_err)}
    .balign 8
cstr_ct_ours:
    .byte {b2a(cstr_ct_ours)}
    .balign 8
cstr_ct_old:
    .byte {b2a(cstr_ct_old)}
    .balign 8
cstr_ct_gone:
    .byte {b2a(cstr_ct_gone)}
    .balign 8
cstr_d8_start:
    .byte {b2a(cstr_d8_start)}
    .balign 8
cstr_d8_dsdt:
    .byte {b2a(cstr_d8_dsdt)}
    .balign 8
cstr_d8_map_lp:
    .byte {b2a(cstr_d8_map_lp)}
    .balign 8
cstr_d8_map_nf:
    .byte {b2a(cstr_d8_map_nf)}
    .balign 8
cstr_d8_ga:
    .byte {b2a(cstr_d8_ga)}
    .balign 8
cstr_d8_a:
    .byte {b2a(cstr_d8_a)}
    .balign 8
cstr_d8_ca:
    .byte {b2a(cstr_d8_ca)}
    .balign 8
cstr_d8_cw:
    .byte {b2a(cstr_d8_cw)}
    .balign 8
cstr_d8_patch_ok:
    .byte {b2a(cstr_d8_patch_ok)}
    .balign 8
cstr_d8_no_dsdt:
    .byte {b2a(cstr_d8_no_dsdt)}
    .balign 8
lstr_entry:
    .byte {a2a(LOG_STRS["entry"])}
    .balign 8
lstr_start:
    .byte {a2a(LOG_STRS["start"])}
    .balign 8
lstr_log_open:
    .byte {a2a(LOG_STRS["log_open"])}
    .balign 8
lstr_log_fail:
    .byte {a2a(LOG_STRS["log_fail"])}
    .balign 8
lstr_acpi_loc:
    .byte {a2a(LOG_STRS["acpi_loc"])}
    .balign 8
lstr_acpi_ok:
    .byte {a2a(LOG_STRS["acpi_ok"])}
    .balign 8
lstr_acpi_fail:
    .byte {a2a(LOG_STRS["acpi_fail"])}
    .balign 8
lstr_ssdt_call:
    .byte {a2a(LOG_STRS["ssdt_call"])}
    .balign 8
lstr_ssdt_ok:
    .byte {a2a(LOG_STRS["ssdt_ok"])}
    .balign 8
lstr_ssdt_fail:
    .byte {a2a(LOG_STRS["ssdt_fail"])}
    .balign 8
lstr_sfs_scan:
    .byte {a2a(LOG_STRS["sfs_scan"])}
    .balign 8
lstr_sfs_fail:
    .byte {a2a(LOG_STRS["sfs_fail"])}
    .balign 8
lstr_found:
    .byte {a2a(LOG_STRS["found"])}
    .balign 8
lstr_load_call:
    .byte {a2a(LOG_STRS["load_call"])}
    .balign 8
lstr_load_ok:
    .byte {a2a(LOG_STRS["load_ok"])}
    .balign 8
lstr_load_fail:
    .byte {a2a(LOG_STRS["load_fail"])}
    .balign 8
lstr_start_img:
    .byte {a2a(LOG_STRS["start_img"])}
    .balign 8
lstr_done_fail:
    .byte {a2a(LOG_STRS["done_fail"])}
    .balign 8
log_path_utf16:
    .byte {b2a(log_path_utf16)}
    .balign 8
bootmgfw_utf16:
    .byte {b2a(bootmgfw_utf16)}
    .balign 8
table_key:
    .quad 0
acpi_proto_ptr:
    .quad 0
handle_count:
    .quad 0
handle_buffer_ptr:
    .quad 0
sfs_ptr:
    .quad 0
root_ptr:
    .quad 0
file_ptr:
    .quad 0
devpath_ptr:
    .quad 0
new_devpath_ptr:
    .quad 0
win_handle:
    .quad 0
log_hcount:
    .quad 0
log_hbuf:
    .quad 0
log_sfs_ptr:
    .quad 0
log_root_ptr:
    .quad 0
log_marker_ptr:
    .quad 0
log_file_ptr:
    .quad 0
log_write_size:
    .quad 0
    .balign 8
ssdt_aml_path_utf16:
    .byte {b2a(ssdt_aml_path_utf16)}
    .balign 8
acpi_guid:
    .byte {b2a(ACPI_GUID)}
    .balign 8
sfs_guid:
    .byte {b2a(SFS_GUID)}
    .balign 8
dp_guid:
    .byte {b2a(DP_GUID)}
    .balign 8
var_name_utf16:
    .byte {b2a(var_name_utf16)}
    .balign 8
var_guid:
    .byte {b2a(VAR_GUID)}
    .balign 8
acpi20_guid_lo:
    .quad 0x11D3E4F18868E871
    .balign 8
acpi20_guid_hi:
    .quad 0x81883CC7800022BC
    .balign 8
map_proto_guid:
    .byte {b2a(MAP_GUID)}
    .balign 8
map_proto_ptr:
    .quad 0
nvs_base_addr:
    .quad 0
    .balign 8
d8_attrs:
    .quad 0
    .balign 8
d8_hex_buf:
    .quad 0
    .quad 0
    .quad 0
    .quad 0
    .quad 0
    .balign 8
ssdt_data:
    .byte {b2a(ssdt_bytes)}
"""

ks = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
try:
    code, count = ks.asm(ASM, as_bytes=True)
except Exception as e:
    print(f"Assembly error: {e}")
    sys.exit(1)

code = bytes(code)
print(f"Assembled: {count} instructions, {len(code)} bytes")
print(f"SKIP_ACPI = {SKIP_ACPI}")

# ---- PE/COFF constants ------------------------------------------------
IMAGE_BASE    = 0x0000000000010000
SECTION_ALIGN = 0x1000
FILE_ALIGN    = 0x200
HDR_SIZE      = 0x200

# ---- .text section ----------------------------------------------------
code_padded   = code + b'\x00' * (-len(code) % FILE_ALIGN)
text_vaddr    = SECTION_ALIGN
text_rawsz    = len(code_padded)
text_vsize    = len(code)
entry_rva     = text_vaddr

# ---- .reloc section (empty BASE_RELOCATION block) ---------------------
# Minimal valid content: one block header (8 bytes), no entries.
# PageRVA=0, BlockSize=8 means: "relocations for page at RVA 0, no entries."
# The UEFI PE loader processes this as zero relocations applied.
reloc_data_raw  = struct.pack("<II", 0, 8)
reloc_padded    = reloc_data_raw + b'\x00' * (-len(reloc_data_raw) % FILE_ALIGN)
reloc_vaddr     = text_vaddr + (-text_vsize % SECTION_ALIGN) + text_vsize
# Round up to SECTION_ALIGN boundary:
reloc_vaddr     = (text_vaddr + text_vsize + SECTION_ALIGN - 1) & ~(SECTION_ALIGN - 1)
reloc_rawsz     = len(reloc_padded)
reloc_rawoff    = HDR_SIZE + text_rawsz   # already FILE_ALIGN-aligned

size_of_image   = (reloc_vaddr + reloc_rawsz + SECTION_ALIGN - 1) & ~(SECTION_ALIGN - 1)

# ---- DOS stub + PE signature ------------------------------------------
dos    = b"MZ" + b'\x00' * 58 + struct.pack("<I", 0x40)
assert len(dos) == 0x40
pe_sig = b"PE\x00\x00"

# ---- COFF header -------------------------------------------------------
# Characteristics 0x020E = EXECUTABLE_IMAGE | LINE_NUMS_STRIPPED |
#                          LOCAL_SYMS_STRIPPED | DEBUG_STRIPPED
#                 (matches GRUB's working EFI binary)
coff = struct.pack("<HHIIIHH",
    0xAA64,  # Machine
    2,       # NumberOfSections (now 2: .text + .reloc)
    0,       # TimeDateStamp
    0,       # PointerToSymbolTable
    0,       # NumberOfSymbols
    0xF0,    # SizeOfOptionalHeader
    0x020E)  # Characteristics

# ---- Optional header ---------------------------------------------------
# DllCharacteristics = 0x0100 (IMAGE_DLLCHARACTERISTICS_NX_COMPAT)
#   Required by Qualcomm/Insyde UEFI PE loader (same as GRUB).
# NumberOfRvaAndSizes = 16 (standard; DataDirectory[5] points to .reloc)
opt_fixed = struct.pack("<HBBIIIIIQIIHHHHHHIIIIHHQQQQII",
    0x020B,          # Magic PE32+
    14, 0,           # MajorLinker, MinorLinker
    text_rawsz,      # SizeOfCode
    reloc_rawsz,     # SizeOfInitializedData
    0,               # SizeOfUninitializedData
    entry_rva,       # AddressOfEntryPoint
    text_vaddr,      # BaseOfCode
    IMAGE_BASE,      # ImageBase
    SECTION_ALIGN,   # SectionAlignment
    FILE_ALIGN,      # FileAlignment
    0, 0,            # MajorOS, MinorOS
    0, 0,            # MajorImage, MinorImage
    0, 0,            # MajorSubsystem, MinorSubsystem
    0,               # Win32VersionValue
    size_of_image,   # SizeOfImage
    HDR_SIZE,        # SizeOfHeaders
    0,               # CheckSum
    0x000A,          # Subsystem = EFI_APPLICATION
    0x0100,          # DllCharacteristics = NX_COMPAT
    0, 0,            # SizeOfStackReserve, Commit
    0, 0,            # SizeOfHeapReserve, Commit
    0,               # LoaderFlags
    16)              # NumberOfRvaAndSizes

# DataDirectory: 16 × 8 bytes, all zeros except [5] (Base Relocation)
datadir = bytearray(16 * 8)
struct.pack_into("<II", datadir, 5 * 8, reloc_vaddr, len(reloc_data_raw))
opt = opt_fixed + bytes(datadir)
assert len(opt) == 0xF0, f"opt header size mismatch: {len(opt)}"

# ---- Section headers --------------------------------------------------
sec_text = struct.pack("<8sIIIIIIHHI",
    b".text\x00\x00\x00",
    text_vsize, text_vaddr,
    text_rawsz, HDR_SIZE,
    0, 0, 0, 0,
    0xE0000020)   # CODE | MEM_EXECUTE | MEM_READ | MEM_WRITE

sec_reloc = struct.pack("<8sIIIIIIHHI",
    b".reloc\x00\x00",
    len(reloc_data_raw), reloc_vaddr,
    reloc_rawsz,         reloc_rawoff,
    0, 0, 0, 0,
    0x42000040)   # CNT_INITIALIZED_DATA | MEM_READ | MEM_DISCARDABLE

# ---- Assemble PE -------------------------------------------------------
headers = dos + pe_sig + coff + opt + sec_text + sec_reloc
assert len(headers) <= HDR_SIZE, f"headers too large: {len(headers)}"
headers += b'\x00' * (HDR_SIZE - len(headers))

pe = headers + code_padded + reloc_padded
print(f"PE size: {len(pe)} bytes  (.text={text_rawsz}  .reloc={reloc_rawsz})")

out = r"C:\Drivers\AcpiInject.efi"
with open(out, "wb") as f:
    f.write(pe)

# ---- Verify written binary -------------------------------------------
with open(out, "rb") as f:
    data = f.read()
pe_off    = struct.unpack_from("<I", data, 0x3C)[0]
opt_off   = pe_off + 24
machine   = struct.unpack_from("<H", data, pe_off + 4)[0]
num_secs  = struct.unpack_from("<H", data, pe_off + 6)[0]
coff_ch   = struct.unpack_from("<H", data, pe_off + 22)[0]
subsys    = struct.unpack_from("<H", data, opt_off + 68)[0]
dll_ch    = struct.unpack_from("<H", data, opt_off + 70)[0]
erva      = struct.unpack_from("<I", data, opt_off + 16)[0]
num_dirs  = struct.unpack_from("<I", data, opt_off + 108)[0]
reloc_dir_va   = struct.unpack_from("<I", data, opt_off + 112 + 5*8)[0]
reloc_dir_size = struct.unpack_from("<I", data, opt_off + 112 + 5*8 + 4)[0]
sec1_ch   = struct.unpack_from("<I", data, pe_off + 24 + 0xF0 + 36)[0]
print(f"Machine=0x{machine:04X}  NumSections={num_secs}  CoffChars=0x{coff_ch:04X}")
print(f"Subsystem=0x{subsys:04X}  DllChars=0x{dll_ch:04X}  EntryRVA=0x{erva:X}")
print(f"NumDirEntries={num_dirs}  .reloc dir: VA=0x{reloc_dir_va:X} Size={reloc_dir_size}")
print(f".text SectionFlags=0x{sec1_ch:08X}")
print(f"Written: {out}")


# Repo Navigation Map — Acer A14-11M Research

> Navigation hub for the research repository. Every concept, attempt, hardware ID,
> protocol, and registry path has a stable address here. For the research paper
> itself, see [`FINDINGS.md`](FINDINGS.md). For the executive summary, see
> [`../README.md`](../README.md).

---

## §1 Reading paths

Three suggested starting points depending on what the reader wants from this repo.

**"I have 10 minutes."** Read [`../README.md`](../README.md). It covers the
hardware, the bug, the root cause, the status, and the open paths.

**"I want the science."** Read [`FINDINGS.md`](FINDINGS.md) start to finish. It is
the synthesised research paper, 13 sections, ~1000 lines. Skip to specific findings
via the topical map in §2 of this file.

**"I want to extend the work."** Start with [`FINDINGS.md §11`](FINDINGS.md)
(Open questions), then [`ATTEMPTS.md`](ATTEMPTS.md) "Remaining paths" for the
structured to-do list, then drill into [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md)
and [`SESSION_LOG.md`](SESSION_LOG.md) as needed for full chronological detail.

### By role

- **OEM/silicon engineer escalating internally** → [`FINDINGS.md §6`](FINDINGS.md)
  (root cause) + [`FINDINGS.md §9`](FINDINGS.md) (memory model) +
  [`FINDINGS.md §10`](FINDINGS.md) (vendor response so far).
- **Buyer evaluating the SKU** → [`../README.md`](../README.md) "Status" section
  + [`FINDINGS.md §10`](FINDINGS.md) (vendor support response).
- **Researcher reproducing the work** → [`FINDINGS.md §12`](FINDINGS.md)
  (Reproducibility) + [`efi-injection/README.md`](../efi-injection/README.md)
  (build and deploy).
- **Community contributor with related-SKU experience** →
  [`FINDINGS.md §11`](FINDINGS.md) (Open questions) + [`ATTEMPTS.md`](ATTEMPTS.md).

---

## §2 Topical map

Topics in reading order, not alphabetical. Each entry names where the topic is
*defined* (the canonical treatment) and where it is *referenced* (cross-references).

### Install method and clean-install failure profile
- **Why it matters:** misframing the install method (as in earlier drafts of
  this work) leads readers to conclude the bug is specific to offline DISM
  applies. The same failure profile occurs after a normal 26H1 USB install
  on a vanilla NX.JP3ED.002 unit.
- **Defined in:** [`FINDINGS.md §3`](FINDINGS.md) — Problem statement, including
  the caccialdo-gist citation of t0ma5's install procedure and the offline-DISM
  footnote.
- **Referenced in:** [`../README.md`](../README.md) "The problem";
  [`SESSION_LOG.md`](SESSION_LOG.md) Sessions 1–3.

### Safe single-INF driver recovery
- **Why it matters:** approximately 60% of the Qualcomm stack can be restored
  this way. The remaining 40% is the cluster blocked by §6.
- **Defined in:** [`FINDINGS.md §5`](FINDINGS.md) — Finding 1: what works.
- **Referenced in:** [`../README.md`](../README.md) "What works after safe
  single-INF install" + "Safe install order for platform drivers";
  [`Driver_Reference_Map.md`](Driver_Reference_Map.md) full catalogue;
  [`SESSION_LOG.md`](SESSION_LOG.md) Sessions 4–22 phase logs.

### The QCSP / SPSS circular `_DEP` deadlock (the root cause)
- **Why it matters:** this is the cause of every downstream failure — ADSP,
  CDSP, Bluetooth radio, audio, Adreno GPU, battery, and the QCPEP cluster
  (17 thermal/policy devices).
- **Defined in:** [`FINDINGS.md §6`](FINDINGS.md) — Finding 2: the root cause,
  with DSDT byte offsets and the cascade of downstream failures.
- **Referenced in:** [`../README.md`](../README.md) "Root cause";
  [`ATTEMPTS.md`](ATTEMPTS.md) "Goal" section;
  [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md) "Goal" section;
  [`SESSION_LOG.md`](SESSION_LOG.md) Sessions 9–15.

### Standard ACPI override mechanisms — and why they all fail on ARM64
- **Why it matters:** these are the obvious mechanisms a Windows user would
  reach for. Each fails for a different architectural reason; documenting all
  four prevents future investigators from re-running them.
- **Defined in:** [`FINDINGS.md §7`](FINDINGS.md) — Finding 3: registry,
  ESP SSDTs, BCD, GRUB2.
- **Referenced in:** [`ATTEMPTS.md`](ATTEMPTS.md) rows 1–4;
  [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md) Attempts 1–4;
  [`SESSION_LOG.md`](SESSION_LOG.md) Sessions 16–25.

### UEFI injection — the 15 sub-attempts (5a–5o)
- **Why it matters:** the bulk of the technical investigation. Each sub-attempt
  uncovers a new platform-specific blocker; together they characterise the
  firmware protection model.
- **Defined in:** [`FINDINGS.md §8`](FINDINGS.md) — Finding 4: narrative of all
  fifteen sub-attempts plus the wrong-GUID bug.
- **Referenced in:** [`ATTEMPTS.md`](ATTEMPTS.md) rows 5a–5o;
  [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md) full chronological
  log; [`AcpiInject_Findings.md`](AcpiInject_Findings.md) wrong-GUID analysis;
  [`efi-injection/README.md`](../efi-injection/README.md) build summary;
  [`SESSION_LOG.md`](SESSION_LOG.md) Sessions 26–41.

### Firmware-managed read-only ACPI memory (the deepest finding)
- **Why it matters:** explains why §8 is exhausted. The firmware enforces
  write-protection on the entire ACPI chain (RSDP, XSDT, FADT, DSDT) AND
  blocks every diagnostic channel from a UEFI app. The combination is what
  is platform-specific.
- **Defined in:** [`FINDINGS.md §9`](FINDINGS.md) — Finding 5: the five facts of
  the protection model.
- **Referenced in:** [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md)
  Attempts 5h–5l; [`SESSION_LOG.md`](SESSION_LOG.md) Session 41.

### Diagnostic methods (oracles, baseline CSVs)
- **Why it matters:** the discipline that made the investigation tractable.
  Without the PIL TZ `Linked` oracle and the DSDT byte oracle, "did the
  injection work?" would not be answerable from Windows.
- **Defined in:** [`FINDINGS.md §4`](FINDINGS.md) — Methodology: PIL TZ
  `Linked=1` oracle, DSDT byte oracle, baseline CSV diffing.
- **Referenced in:** [`ATTEMPTS.md`](ATTEMPTS.md) "Diagnostic oracle" block;
  [`SESSION_LOG.md`](SESSION_LOG.md) passim.

### Vendor support response (Acer)
- **Why it matters:** the support pathway for an SKU under warranty is part of
  the bug's practical impact. The escalation, the response, and the analysis
  of why the offered remediation is paywalled are documented for accountability.
- **Defined in:** [`FINDINGS.md §10`](FINDINGS.md) — Vendor support response.
- **Referenced in:** [`../README.md`](../README.md) "Vendor support response"
  pointer paragraph.

### Open questions and remaining paths
- **Why it matters:** the hooks where the community or other researchers can
  pick up the work. Each entry includes what evidence would distinguish
  success and the principal risks.
- **Defined in:** [`FINDINGS.md §11`](FINDINGS.md) — four groups, all untried/unproven:
  (a) validation paths that would prove/refute the root cause, (b) candidate fixes
  outside UEFI injection, (c) out-of-band firmware fixes, (d) public disclosure. What
  was exhausted is *in-band ACPI injection from a UEFI boot app* (5a–5o), not every
  avenue.
- **Referenced in:** [`ATTEMPTS.md`](ATTEMPTS.md) "Remaining paths" table;
  [`FINDINGS.md §6 Limitations`](FINDINGS.md) (proof status).

---

## §3 Attempt index

Every numbered attempt, in order, with a one-line outcome and pointers to the
canonical write-up.

### Pre-UEFI attempts (1–4)

- **Attempt 1** — `HKLM\...\acpitables` registry + `bcdedit ACPIOVERRIDETEST`.
  Sessions 16–17. **Dead on ARM64** — registry/BCD mechanism is x86/x64-only.
  → [`FINDINGS.md §7`](FINDINGS.md) Mechanism 1; [`ATTEMPTS.md`](ATTEMPTS.md)
  row 1; [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md) Attempt 1.
- **Attempt 2** — SSDT files at ESP paths. Session 17. **Dead on this
  firmware** — Insyde H2O does not load ESP SSDTs.
  → [`FINDINGS.md §7`](FINDINGS.md) Mechanism 2; [`ATTEMPTS.md`](ATTEMPTS.md)
  row 2.
- **Attempt 3** — Binary-patched DSDT via `acpitables` registry. Sessions
  22–23. **Dead on ARM64** — same registry mechanism as #1.
  → [`FINDINGS.md §7`](FINDINGS.md) Mechanism 3.
- **Attempt 4** — GRUB2 `acpi` module + chainloader. Sessions 23–25. **Dead on
  ARM64** — GRUB modifies XSDT in RAM but does not update the EFI
  ConfigurationTable RSDP pointer.
  → [`FINDINGS.md §7`](FINDINGS.md) Mechanism 4.

### UEFI injection attempts (5a–5o, custom AcpiInject.efi)

- **5a** — GRUB chainloader → AcpiInject.efi. Session 30. **Failed** — Shim
  `EFI_SECURITY_ARCH_PROTOCOL` blocked `LoadImage`.
  → [`FINDINGS.md §8`](FINDINGS.md).
- **5b** — Direct BOOTAA64.EFI. Session 31. **Failed** — PE section missing
  `MEM_WRITE`; ARM64 permission fault.
- **5c** — Added MEM_WRITE + ConOut. Sessions 32–33. **Failed** — invalid
  `NumberOfRvaAndSizes` and `DllCharacteristics`.
- **5d** — Fixed PE headers + `.reloc` section. Sessions 33–34. **Partial** —
  binary ran; wrong `EFI_FILE_PROTOCOL` offsets prevented log file creation.
- **5e** — Fixed file protocol offsets. Sessions 34–35. **Failed** — log
  still absent.
- **5f** — Brute-force SFS scan. Sessions 35–36. **Failed** — USB SFS handle
  not returned by `LocateHandleBuffer`.
- **5g** — Try first NVMe SFS handle. Sessions 36–37. **Failed** — NVMe ESP
  SFS refuses `Open(CREATE)` from UEFI app context.
- **5h** — UEFI NVRAM variable logging via `SetVariable`. Sessions 37–38.
  **Failed** — `GetFirmwareEnvironmentVariableW` returns error 1314 for ALL
  variables including `BootOrder`. Runtime variable services blocked.
- **5i** — Direct XSDT modification. Sessions 38–39. **Failed** — RSDP write
  silently dropped; firmware memory is read-only.
- **5j** — SSDT data in `EfiACPIMemoryNVS`. Sessions 39–40. **Failed** — same
  RSDP write failure as 5i.
- **5k** — DSDT in-place byte patch at offset `0x36C69`. Session 40.
  **Failed** — DSDT pages also read-only; write silently dropped.
- **5l** — `EFI_MEMORY_ATTRIBUTE_PROTOCOL->ClearMemoryAttributes()` then DSDT
  patch. Sessions 40–41. **Failed** — DSDT unchanged; MAP absent or also
  blocked for ACPI memory.
- **5m** — MAP unprotect + canary write to `DSDT[0x20]` (CreatorRevision).
  Sessions 46–47. **Failed** — canary unchanged after boot; DSDT write path
  confirmed permanently closed.
- **5n** — `BootServices->InstallConfigurationTable()` with a new RSDP/XSDT/SSDT
  chain in `EfiACPIMemoryNVS`. Sessions 47–48. **Failed** — only the "Compal"
  SSDT key after boot; replacement chain not parsed by Windows.
- **5o** — 5n plus on-screen `ICT=`/`CT=` diagnostics and a corrected 8-second
  stall. Session 48. **Failed** — tested; SSDT not injected, deadlock not
  broken. The `InstallConfigurationTable()` path is closed.

### The wrong-GUID bug (retrospective)

The `ACPI_GUID` constant embedded in builds 5a–5g was
`{8D59D32B-C655-4AE9-9B15-F25904992A43}` (`EFI_ABSOLUTE_POINTER_PROTOCOL`)
rather than `{FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}` (`EFI_ACPI_TABLE_PROTOCOL`).
This means 5a–5g would not have located the ACPI protocol even if present.
Corrected before 5h. → [`AcpiInject_Findings.md`](AcpiInject_Findings.md).

### Remaining paths

What is exhausted is **in-band ACPI injection from a UEFI boot app** (5a–5o) — not
every avenue. The full, honestly-labeled catalogue (all untried/unproven) is in
[`FINDINGS.md §11`](FINDINGS.md), in four groups:

- **§11a Validation paths** (prove/refute the root cause, do not fix) — factory-image
  comparison (highest value), ETW/Kernel-PnP or WinDbg `_DEP`-gate trace, live-kernel
  DSDT patch, cross-device DSDT comparison, non-Windows `acpidump`. *None attempted.*
- **§11b Candidate fixes not yet attempted** — rEFInd ACPI loading, UEFI Shell
  `acpiview`, alternate/vendor ACPI protocol GUID (`{6DABB78A-…}`), Windows kernel-side
  circumvention (filter driver / phantom devnode / registry override — caveated by
  HVCI/driver-signing), offline boot-start staging of `qcsp.sys`. *None attempted;
  none claimed to work.*
- **§11c Out-of-band firmware fixes** — Acer BIOS V1.10+ (V1.09 latest as of May 2026,
  low risk) and offline BIOS ROM modification (UEFITool/H2OFFT, high brick risk,
  backup required).
- **§11d Public disclosure (this repository)** — no prior public write-up matched the
  QCOM0C87/SPSS `_DEP` deadlock; this repo documents the full failure chain so others
  need not re-derive it.

---

## §4 Glossary

Alphabetical reference. Four sub-sections.

### §4a — Hardware IDs

ACPI device hardware IDs that appear in the research. Each entry: friendly name,
state, and a pointer to where the device is discussed.

- **`ACPI\ACPI0011\0`** — HID Button over Interrupt. `CM_PROB_FAILED_START`.
  See [`Driver_Reference_Map.md`](Driver_Reference_Map.md).
- **`ACPI\QCOM0427`** — Acer base driver shim. Provided by `qcabd.inf`.
  See [`Driver_Reference_Map.md`](Driver_Reference_Map.md).
- **`ACPI\QCOM06D9`** — Qualcomm Human Presence Sensor. WUDFRd fails.
- **`ACPI\QCOM0C04`** — Watchdog timer HAL extension.
- **`ACPI\QCOM0C11`** — Qualcomm ADC. `CM_PROB_FAILED_START`.
- **`ACPI\QCOM0C16`** — Qualcomm Bus Device (UART). `CM_PROB_FAILED_ADD`.
- **`ACPI\QCOM0C1B`** — **ADSP** (Qualcomm Audio DSP Subsystem).
  `CM_PROB_FAILED_ADD`. Blocked by the `_DEP` deadlock.
  See [`FINDINGS.md §6`](FINDINGS.md).
- **`ACPI\QCOM0C2A`** — Battery mini class.
- **`ACPI\QCOM0C2F`** — CDI (CDSP interface).
- **`ACPI\QCOM0C32\1B`** — ISP Camera Platform. `CM_PROB_FAILED_INSTALL`.
- **`ACPI\QCOM0C58`, `0C59`, `0C5A`, `0C91`, `0CBF`** — temperature sensors
  inside the QCPEP cluster. `CM_PROB_FAILED_ADD`.
- **`ACPI\QCOM0C5C`** — ADSP RPC.
- **`ACPI\QCOM0C82`** — ADSP RPC daemon.
- **`ACPI\QCOM0C87`** — **QCSP** (Qualcomm Secure Platform Device). Absent
  from PnP because of the `_DEP` deadlock. The SSDT-injection target.
  See [`FINDINGS.md §6`](FINDINGS.md) and §8.
- **`ACPI\QCOM0C8D`** — **SPSS** (Qualcomm Secure Processor Subsystem).
  `CM_PROB_FAILED_ADD`. Drives the deadlock from the SPSS side.
- **`ACPI\QCOM0CA8`** — Connection Security Device. **OK** after install.
- **`ACPI\QCOM0CB0`** — **CDSP** (Qualcomm Compute DSP Subsystem).
  `CM_PROB_FAILED_ADD`.
- **`ACPI\QCOM0CD5`** — Subsys Thermal Mitigation. `CM_PROB_FAILED_ADD`.
- **`ACPI\QCOM0CF1`** — EVA Device. `CM_PROB_FAILED_INSTALL`.
- **`ACPI\QCOM0D04`** — BT ACX transport. **OK** after install.
- **`ACPI\QCOM0D05`** — Fan EC Interface. `CM_PROB_FAILED_ADD`.
- **`ACPI\QCOM0D06`** — Always-on sensing.
- **`ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CRD08380`** — Bluetooth radio. Not enumerated.
- **`ACPI\VEN_QCOM&DEV_0CF2..0CFC`** — CPU/GPU/NPU/WLAN/Modem policy devices
  inside the QCPEP cluster. `CM_PROB_FAILED_ADD`.

Full HWID-to-INF mapping with versions, package origins, and install status:
[`Driver_Reference_Map.md`](Driver_Reference_Map.md).

### §4b — UEFI protocols and GUIDs

UEFI protocols and ConfigurationTable GUIDs referenced in the research, with
their state on this platform.

- **`EFI_ABSOLUTE_POINTER_PROTOCOL`** — GUID
  `{8D59D32B-C655-4AE9-9B15-F25904992A43}`. Used incorrectly as the ACPI
  protocol GUID in `build_efi.py` builds 5a–5g (the wrong-GUID bug).
  See [`AcpiInject_Findings.md`](AcpiInject_Findings.md);
  [`FINDINGS.md §8`](FINDINGS.md).
- **`EFI_ACPI_20_TABLE_GUID`** — `{8868E871-E4F1-11D3-BC22-0080C73C8881}`. The
  ConfigurationTable entry that points to the ACPI 2.0 RSDP. The target of
  Attempts 5i/5j (write to existing RSDP) and of the un-attempted
  `InstallConfigurationTable()` path in [`FINDINGS.md §11`](FINDINGS.md).
- **`EFI_ACPI_TABLE_PROTOCOL`** — `{FFE06BDD-6107-46A6-7BB2-5A9C7EC5275C}`.
  The correct protocol for `InstallAcpiTable()`. Attempt 5h could not
  conclusively distinguish "protocol absent" from "InstallAcpiTable rejected"
  because the wrong GUID was used in earlier builds and no diagnostic channel
  was available by 5h.
- **`EFI_MEMORY_ATTRIBUTE_PROTOCOL`** — UEFI 2.10, GUID
  `{6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14}`. Attempted in 5l for unprotecting
  ACPI pages. Absent or non-functional on Insyde H2O V1.09.
  See [`FINDINGS.md §9`](FINDINGS.md).
- **`EFI_SECURITY_ARCH_PROTOCOL`** — used by Shim to gate `LoadImage`. Blocked
  the unsigned `AcpiInject.efi` in Attempt 5a.
  See [`FINDINGS.md §8`](FINDINGS.md).
- **`EFI_SIMPLE_FILE_SYSTEM_PROTOCOL`** — used to attempt log file creation.
  USB SFS handle not returned by `LocateHandleBuffer` (5f); NVMe ESP SFS
  refuses `Open(CREATE)` (5g).
- **`BootOrder` UEFI variable** — vendor GUID
  `{8BE4DF61-93CA-11D2-AA0D-00E098032B8C}`. Standard global variable;
  unreadable from Windows on this firmware (error 1314), as is every other
  variable tested. Discovered in Attempt 5h.
- **`EFI_FILE_PROTOCOL`** — used in Attempts 5d–5g for log file creation.
  Sub-attempt-specific issues: wrong vtable offsets (`Write` is at +40 not
  +56, `Flush` is at +80), USB SFS not enumerated, NVMe ESP SFS refuses
  CREATE.
- **`EFI_SYSTEM_TABLE`** — the root structure passed to the UEFI application's
  entry point. The `ConfigurationTable` array is the entry point for the
  ACPI 2.0 GUID lookup in Attempts 5i, 5j, and the un-attempted
  `InstallConfigurationTable()` path.
- **PE32+ AARCH64 format requirements** — for a UEFI ARM64 application to load
  on this firmware: `NumberOfRvaAndSizes` must equal 16,
  `DllCharacteristics` must include the `NX_COMPAT` flag (e.g. `0x0100`),
  and a `.reloc` section must be present. Sections that store global state
  must have `MEM_WRITE`. Discovered across Attempts 5b, 5c, and 5d.
- **`EFI_MEMORY_RO` page attribute** — the bit that
  `EFI_MEMORY_ATTRIBUTE_PROTOCOL->ClearMemoryAttributes()` would clear.
  Equal to `0x00020000`. Attempt 5l targets this attribute on DSDT pages.

### §4c — Registry paths and oracles

Windows registry paths the investigation reads or writes for diagnosis.

- **`HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000`** — Windows'
  live ACPI DSDT byte array. The byte oracle at offset `0x36C69` reads from
  here. See [`FINDINGS.md §4`](FINDINGS.md), §6, and §8.
- **`HKLM\HARDWARE\ACPI\SSDT`** — installed SSDT tables. A new `QCOMM_` key
  appearing here would indicate an injected SSDT was parsed by Windows.
- **`HKLM\SYSTEM\CurrentControlSet\Control\acpitables`** — the x86/BIOS
  registry-based ACPI override path. Dead on Windows ARM64.
- **`HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}\#`** —
  PIL TZ device interface state. `Linked=1` indicates the deadlock is broken.
- **`HKLM\SYSTEM\CurrentControlSet\Services\qcsp`** — where the service entry
  for `qcsp.sys` lives if the driver is staged. Present even when QCSP is
  not enumerated; staging is not sufficient — Windows must also present the
  device.
- **`HKLM\SYSTEM\CurrentControlSet\Enum\ACPI\QCOM0C87`** — would appear here
  if QCSP were presented to PnP. Currently absent from PnP because of the
  `_DEP` deadlock. Successful injection would populate this key.
- **`HKLM\HARDWARE\DESCRIPTION\System\BIOS`** — `SystemBiosVersion` and
  `BIOSVersion` values; primary read path for confirming Insyde firmware
  version from inside Windows.

### §4d — DSDT byte offsets

Specific offsets within the live DSDT used in the investigation.

- **`DSDT[0x36C69..0x36C6C]`** — the `_DEP[2]` name field on QCSP. Reads
  `53 50 53 53` ("SPSS") in the broken state; `47 4C 4E 4B` ("GLNK") would
  break the deadlock if writable. See [`FINDINGS.md §6`](FINDINGS.md).
- **`DSDT[0x20..0x23]`** — the DSDT CreatorRevision field, used as the benign
  canary target in Attempt 5m. A known pattern written here after a MAP unprotect
  attempt never appeared in the registry, confirming firmware-managed ACPI pages
  silently drop writes. See [`FINDINGS.md §8`](FINDINGS.md).

---

## §5 Document map

Every published file in the repository and what it contains, including
approximate length.

| File | Lines | Contents |
|---|---|---|
| [`../README.md`](../README.md) | ~220 | Executive summary, current status, repository layout, vendor-response pointer |
| [`FINDINGS.md`](FINDINGS.md) | ~1000 | Synthesised research paper; 13 sections covering problem statement, methodology, findings 1–5, vendor response, open questions, reproducibility |
| [`INDEX.md`](INDEX.md) | this file | Navigation map: reading paths, topical map, attempt index, glossary, document map |
| [`SESSION_LOG.md`](SESSION_LOG.md) | ~6550 | Chronological lab notebook, 48 sessions. The primary source artifact for every finding in FINDINGS.md |
| [`ATTEMPTS.md`](ATTEMPTS.md) | ~85 | Concise table of all attempts (1–4 standard, 5a–5o UEFI) plus remaining out-of-band paths |
| [`EFI_Injection_Tracking.md`](EFI_Injection_Tracking.md) | ~690 | Full chronological log of UEFI injection sub-attempts 5a–5o with binary sizes, hex dumps, and post-boot diagnostics |
| [`AcpiInject_Findings.md`](AcpiInject_Findings.md) | ~500 | Snapshot analysis of `build_efi.py`; identified the wrong-GUID bug and detailed the assembly-level runtime behaviour |
| [`Driver_Reference_Map.md`](Driver_Reference_Map.md) | ~325 | Hardware ID to INF mapping for the entire Qualcomm driver package set |
| [`../efi-injection/README.md`](../efi-injection/README.md) | ~135 | Build and deploy instructions for `AcpiInject.efi` plus the 5a–5o attempt summary |
| [`../efi-injection/build_efi.py`](../efi-injection/build_efi.py) | ~700 | Python builder that assembles `AcpiInject.efi` (PE32+ AARCH64) |
| [`../efi-injection/ssdt_qcsp.asl`](../efi-injection/ssdt_qcsp.asl) | ~15 | ASL source for the stub SSDT (human-readable) |
| `../efi-injection/ssdt_qcsp.aml` | (binary) | Compiled SSDT binary, 80 bytes |
| `../baselines/*.csv` | (data) | Four milestone PnP device snapshots taken at key investigation phases |

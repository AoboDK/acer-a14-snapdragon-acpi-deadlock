# Vendor Summary: Acer A14-11M Qualcomm ACPI Dependency Deadlock

**For:** Acer, Qualcomm, Insyde, or Microsoft firmware/driver engineering teams
**Date:** 2026-06-09
**Full documentation:** https://github.com/AoboDK/acer-a14-snapdragon-acpi-deadlock

---

## Device

| Field | Value |
|---|---|
| Model | Acer Swift 14 AI A14-11M |
| Product code | NX.JP3ED.002 |
| SoC | Qualcomm Snapdragon X 8380 (SUBSYS_CRD08380) |
| Firmware | Insyde H2O (QCOMM_/SDM8380_/rev3), V1.09 |
| OS | Windows 11 ARM64 26H1, Build 26200 |

---

## Symptom

After a clean Windows 11 ARM64 installation on this SKU — using an official
Microsoft ISO, following standard procedures — approximately 40 Qualcomm platform
devices fail to start. The affected devices include:

- ADSP, CDSP, and SPSS (`CM_PROB_FAILED_ADD`)
- A cluster of 17 QCPEP thermal and policy devices (`STATUS_NO_SUCH_DEVICE`)
- Adreno GPU
- Bluetooth radio (transport present; radio device absent)
- Audio (blocked by ADSP failure)
- Battery reporting (blocked)

The QCSP device (`ACPI\QCOM0C87`) does not appear in the Windows PnP device
tree at all.

---

## Core finding

The DSDT shipped with Insyde H2O V1.09 for this SKU defines the QCSP device as:

```asl
Device (QCSP) {
    Name (_HID, "QCOM0C87")
    Name (_STA, 0x0F)
    Name (_DEP, Package() { \_SB.GLNK, \_SB.SOCP, \_SB.SPSS })
}
```

This creates a circular dependency that Windows cannot resolve:

1. QCSP carries `_DEP` on `\_SB.SPSS` — Windows withholds QCSP until SPSS is
   functional.
2. SPSS (`ACPI\QCOM0C8D`) fails at runtime with `CM_PROB_FAILED_ADD` /
   `STATUS_OBJECT_NAME_NOT_FOUND` — the PIL TZ device interface is not active.
3. The PIL TZ interface (`{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}`) is published
   by `qcsp.sys` — the driver for the QCSP device.
4. `qcsp.sys` cannot load because QCSP is never presented to the PnP manager.
5. Loop is complete and self-sustaining.

No driver installation can break this loop. The relevant `qcsp.sys` INFs are staged
and present in the driver store; the device they match is simply never presented.

---

## Evidence

| Signal | Observation | How to verify |
|---|---|---|
| QCSP absent from PnP | `Get-PnpDevice` returns no `QCOM0C87` entry; Kernel-PnP log (732 events) has zero entries for `ACPI\QCOM0C87`; `HKLM\...\Enum\ACPI` has no `QCOM0C87` subkey | `Get-PnpDevice -PresentOnly \| Where-Object { $_.InstanceId -like "*QCOM0C87*" }` → no output |
| SPSS failing | `CM_PROB_FAILED_ADD`, `STATUS_OBJECT_NAME_NOT_FOUND` | `Get-PnpDevice \| Where-Object { $_.InstanceId -like "*QCOM0C8D*" }` |
| SPSS start held pending | Live kernel debugger: `DOE_START_PENDING` on the SPSS device object | `bcdedit /debug on` → `kdARM64.exe -kl` → `!devobj` on SPSS PDO |
| Windows dependency database records QCSP as SPSS's dependent | `DEVPKEY_Device_DependencyDependents` on SPSS = `\_SB.QCSP` (ACPI namespace path, used for never-presented devices) | `Get-PnpDeviceProperty -InstanceId "ACPI\QCOM0C8D\..." -KeyName DEVPKEY_Device_DependencyDependents` |
| PIL TZ interface inactive | `Linked` value blank at `HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-...}\#` | PowerShell: `Get-ChildItem $base -Recurse \| Get-ItemProperty \| Select-Object PSPath, Linked` |
| DSDT `_DEP` structure | QCSP's `_DEP` package includes `\_SB.SPSS` at byte offset `0x36C69` | `HKLM\HARDWARE\ACPI\DSDT\QCOMM_\SDM8380_\00000003\00000000` at `[0x36C69..0x36C6C]` = `53 50 53 53` ("SPSS") |

Full reproduction procedure and exact commands: [`reproduce.md`](reproduce.md).
Full evidence with session-by-session context: [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md).

---

## The fix

The byte change required is minimal and precisely known:

**In the DSDT, at offset `0x36C69`:**

```
Before: 53 50 53 53  ("SPSS")
After:  47 4C 4E 4B  ("GLNK")
```

This replaces the `_DEP[2]` reference from `\_SB.SPSS` (which fails) to `\_SB.GLNK`
(which starts successfully), eliminating the circular dependency. After this change,
QCSP is presented to PnP, `qcsp.sys` loads, PIL TZ activates, and SPSS can complete
`AddDevice`.

Alternatively: removing `\_SB.SPSS` from QCSP's `_DEP` package entirely would
achieve the same result.

---

## Requested action

**Release a BIOS update for product code NX.JP3ED.002** that:

- Removes `\_SB.SPSS` from the QCSP device's `_DEP` package in the DSDT, or
- Changes the DSDT/initialization order so QCSP and `qcsp.sys` can initialize before
  SPSS requires the PIL TZ interface.

Verification: after a BIOS update, `ACPI\QCOM0C87` should appear in PnP and
`HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E2EB84C1-4068-4994-A48F-F3AC0D38DC29}\#`
should show `Linked=1`.

---

## Workaround status

| Workaround | Status |
|---|---|
| Safe single-INF driver installation | Works — restores ~60% of the platform stack, not the full stack |
| Acer's bundled `Setup_Driver.cmd` | **Unsafe** in this state — causes "SOC critical device removed" BSOD |
| Windows Update | Does not address this issue |
| Factory recovery media | May restore the original working OEM state, but is not a firmware fix and does not apply to clean reinstalls |
| UEFI injection (15 sub-attempts) | All in-band paths blocked — ACPI memory is firmware-managed read-only on this platform |

No complete software-only recovery path has been confirmed. Two UEFI protocol
retests (D8a: `EFI_ACPI_TABLE_PROTOCOL`; D8b: `EFI_MEMORY_ATTRIBUTE_PROTOCOL`)
with corrected GUIDs are pending; results will be published in this repository.

---

## Support timeline

| Date | Event |
|---|---|
| May 2026 | Detailed technical writeup submitted to Acer support |
| 22 May 2026 | Single reply received: Windows Update + purchase recovery media |
| 8 June 2026 | No further response — 17 days of silence |

The recovery media option requires payment and physical delivery lead time on an
in-warranty, hardware-defect-free device. The failure was caused by following
standard Microsoft and manufacturer reinstall procedures.

---

## Contact

Aksel Visby — aksel.visby@gmail.com
Repository: https://github.com/AoboDK/acer-a14-snapdragon-acpi-deadlock

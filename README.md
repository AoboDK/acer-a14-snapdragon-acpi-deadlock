# Acer A14-11M — Qualcomm ACPI Dependency Deadlock on Windows 11 ARM64

**Status:** Partial recovery documented. Full software fix not yet achieved.
Two UEFI protocol retests (D8a, D8b) pending. Firmware-level remediation likely required.

---

## What this is

After a clean Windows 11 ARM64 reinstall on the Acer Swift 14 AI (A14-11M,
NX.JP3ED.002, Snapdragon X 8380), roughly 40 Qualcomm platform devices fail to
start — including ADSP, CDSP, SPSS, the QCPEP thermal cluster, Adreno GPU, audio,
and Bluetooth radio.

The root cause is **strongly indicated** to be a circular ACPI `_DEP` dependency
hardcoded in the Insyde H2O V1.09 firmware DSDT:

```
QCSP (ACPI\QCOM0C87)  ←──────────────────────────────┐
  _DEP includes \_SB.SPSS                              │
        │                                               │
        ▼                                               │
Windows withholds QCSP until SPSS resolves             │
        │                                               │
        ▼                                               │
SPSS (ACPI\QCOM0C8D) fails — PIL TZ interface inactive │
        │                                               │
        ▼                                               │
PIL TZ is published by qcsp.sys                        │
        │                                               │
        ▼                                               │
qcsp.sys can't load — QCSP was never presented ────────┘
```

No driver installation can break this loop. A firmware-level fix is required.

---

## Practical warning

**Do not run Acer's bundled `Setup_Driver.cmd`** on a system in this broken state.
It performs a bulk recursive install and triggers a "SOC critical device removed"
BSOD. Use the safe single-INF method documented in [`paper.md §3`](paper.md).

---

## Main documents

| File | Purpose |
|---|---|
| [`paper.md`](paper.md) | Full research paper — start here |
| [`reproduce.md`](reproduce.md) | Minimum reproducible test case *(coming)* |
| [`vendor_summary.md`](vendor_summary.md) | One-page vendor escalation summary *(coming)* |
| [`docs/SESSION_LOG.md`](docs/SESSION_LOG.md) | Chronological lab notebook (54+ sessions) |
| [`docs/ATTEMPTS.md`](docs/ATTEMPTS.md) | Concise attempt summary table |
| [`docs/EFI_Injection_Tracking.md`](docs/EFI_Injection_Tracking.md) | Full UEFI injection sub-attempt log (5a–5o) |
| [`docs/Driver_Reference_Map.md`](docs/Driver_Reference_Map.md) | Hardware ID to INF mapping |
| [`efi-injection/`](efi-injection/) | Python EFI builder, SSDT sources |

---

## What works after safe single-INF recovery

WiFi, display, keyboard, trackpad, USB, camera, NPU, PMIC, GLINK, IPC Router,
IPCC, Syscache, SMMU, PIL, PIL Filter, qcsubsys — all running.

## What is still broken

| Device | Problem |
|---|---|
| ADSP / CDSP / SPSS | `CM_PROB_FAILED_ADD` |
| QCSP (`ACPI\QCOM0C87`) | Absent from PnP entirely |
| QCPEP thermal / policy cluster (17 devices) | `STATUS_NO_SUCH_DEVICE` |
| Adreno GPU | Failing |
| Bluetooth radio | Transport OK; radio not enumerated |
| Audio | Blocked by ADSP |
| Battery reporting | Blocked |

---

## Remediation status

| Path | Status |
|---|---|
| Safe single-INF driver recovery | Works — restores ~60% of the platform |
| `acpitables` registry / ESP SSDT / GRUB ACPI module | Dead on ARM64 / this firmware |
| Custom `AcpiInject.efi` (15 sub-attempts, 5a–5o) | All blocked — ACPI memory is firmware read-only |
| `EFI_ACPI_TABLE_PROTOCOL` (correct GUID) | **Pending D8a retest** |
| `EFI_MEMORY_ATTRIBUTE_PROTOCOL` (correct GUID) | **Pending D8b retest** |
| Post-boot kernel DSDT patch | Attempted — insufficient; `acpi.sys` parses AML once at boot |
| BIOS update from Acer | Not available as of May 2026; requested |
| Offline BIOS ROM mod | Possible but high brick risk; not attempted |

---

## Vendor response

A detailed technical writeup was sent to Acer support. The reply, after seven days,
was four lines: try Windows Update; if that fails, buy physical recovery media.
No escalation to a firmware team. No engagement with the technical content.
No further response as of 8 June 2026.

---

## Hardware

| | |
|---|---|
| Model | Acer Swift 14 AI (A14-11M) — NX.JP3ED.002 |
| SoC | Qualcomm Snapdragon X 8380 (CRD/SUBSYS_CRD08380) |
| OS | Windows 11 ARM64 (build 26200) |
| UEFI | Insyde H2O V1.09 |
| Secure Boot | OFF (disabled for testing) |
| HVCI | ON |

---

## Contributing / related hardware

If you have a Snapdragon X (8cx Gen 4, X Elite, X Plus, or 8380) device with
similar symptoms after a clean Windows reinstall, please open an issue. This may
apply to other Qualcomm CRD-class boards beyond the NX.JP3ED.002.

Relevant upstream projects:
- [WOA-Project/Qualcomm-Reference-Drivers](https://github.com/WOA-Project/Qualcomm-Reference-Drivers)
- [WOA-Project/Mu-Silicium](https://github.com/WOA-Project/Mu-Silicium)

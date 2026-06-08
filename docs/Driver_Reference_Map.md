# Acer A14-11M — Driver Reference Map

> Reference snapshot. HWID → INF mapping is stable; install statuses reflect the
> state at snapshot time. See [`FINDINGS.md §5`](FINDINGS.md) for the recovered
> driver narrative; see [`INDEX.md §4a`](INDEX.md) for the hardware-ID glossary.

**Machine:** Snapdragon X 8380 (SUBSYS_CRD08380) | **OS:** Windows 11 ARM64 26H1

This document maps every available driver package to its hardware IDs so a failing device can be matched to an INF without scanning manually.

---

## Quick-Reference: Currently Failing Devices → Driver Match

| Device / Instance ID | Friendly Name | Problem | Matched INF | Package | Install Status |
|---|---|---|---|---|---|
| `ACPI\QCOM0C1B` | Qualcomm Audio DSP Subsystem | CM_PROB_FAILED_ADD (0xC0000182) | `qcsubsys8380.inf` → oem70.inf | Base 0.7700.1 | **Installed, fails at runtime — SSDT blocker** |
| `ACPI\QCOM0CB0` | Qualcomm Compute DSP Subsystem | CM_PROB_FAILED_ADD (0xC000003B) | `qcsubsys8380.inf` → oem70.inf | Base 0.7700.1 | **Installed, fails at runtime — SSDT blocker** |
| `ACPI\QCOM0C8D` | Qualcomm Secure Processor Subsystem | CM_PROB_FAILED_ADD (0xC000003B) | `qcsubsys8380.inf` → oem70.inf | Base 0.7700.1 | **Installed, fails at runtime — SSDT blocker** |
| `ACPI\QCOM0C87` | Qualcomm Secure Platform Device | Not presented to PnP | `qcsp8380.inf` → oem102/oem103.inf | Base 0.7700.1 + WOA | **Staged — blocked by circular _DEP (see SSDT plan)** |
| `ACPI\QCOM0C5A` | Qualcomm Temperature Sensor | CM_PROB_FAILED_ADD (0xC000000E) | `qcpep.wd8380.inf` → oem89.inf | WOA | **Staged — blocked, qcpep stopped** |
| `ACPI\QCOM0D05` | Qualcomm Fan EC Interface | CM_PROB_FAILED_ADD (0xC000000E) | `qcpep.wd8380.inf` → oem89.inf | WOA | **Staged — blocked, qcpep stopped** |
| `ACPI\QCOM0CBF\1` | Qualcomm Temperature Sensor | CM_PROB_FAILED_ADD (0xC000000E) | `qcpep.wd8380.inf` → oem89.inf | WOA | **Staged — blocked, qcpep stopped** |
| `ACPI\QCOM0C91\0` | Qualcomm Temperature Sensor | CM_PROB_FAILED_ADD (0xC000000E) | `qcpep.wd8380.inf` → oem89.inf | WOA | **Staged — blocked, qcpep stopped** |
| `ACPI\QCOM0C58\0`, `\1` | Qualcomm Temperature Sensor | CM_PROB_FAILED_ADD (0xC000000E) | `qcpep.wd8380.inf` → oem89.inf | WOA | **Staged — blocked, qcpep stopped** |
| `ACPI\QCOM0C59\0`, `\1` | Qualcomm Temperature Sensor | CM_PROB_FAILED_ADD (0xC000000E) | `qcpep.wd8380.inf` → oem89.inf | WOA | **Staged — blocked, qcpep stopped** |
| `ACPI\VEN_QCOM&DEV_0CF2–0CFC` | CPU/GPU/NPU/WLAN/Modem Policy Devices | CM_PROB_FAILED_ADD (0xC000000E) | `qcpep.wd8380.inf` → oem89.inf | WOA | **Staged — blocked, qcpep stopped** |
| `ACPI\QCOM0C11\0` | Qualcomm Analog-to-Digital Converter | CM_PROB_FAILED_START (0xC0000001) | `qcadc8380.inf` | Base 0.7700.1 | **Installed, fails to start** |
| `ACPI\QCOM0C16\F`, `\16` | Qualcomm Bus Device | CM_PROB_FAILED_ADD (0xC000003B) | `qcuart8380.inf` → oem79.inf | Base 0.7700.1 | **Installed, fails AddDevice** |
| `ACPI\QCOM06D9` | Qualcomm Human Presence Sensor | CM_PROB_FAILED_ADD (0xC0000001) | `qcHumanPresenceSensor.inf` → oem35.inf | Base 0.7700.1 | **Installed, WUDFRd fails** |
| `ACPI\QCOM0CD5` | Qualcomm Subsys Thermal Mitigation | CM_PROB_FAILED_ADD (0xC0000001) | `qcSubsysThermalMgr.inf` → oem88.inf | Base 0.7700.1 | **Installed, fails AddDevice** |
| `ACPI\QCOM0CF1` | EVA Device | CM_PROB_FAILED_INSTALL | `qcdxext_qcdpps8380.inf` or `qcdpps8380.inf` | Base 0.7700.1 | **Needs investigation** |
| `ACPI\QCOM0C32\1B` | ISP Camera Platform | CM_PROB_FAILED_INSTALL | Unknown — no clear INF match found | — | **No match — needs investigation** |
| `ACPI\ACPI0011\0` | HID Button over Interrupt | CM_PROB_FAILED_START (0xC000009E) | `hidinterrupt.inf` (Windows built-in) | Windows | **Installed, fails to start** |
| Bluetooth radio | Not enumerated | — | `qcbluetooth8380.inf` (SUBSYS_CRD08380 match exists) | Base 0.7700.1 | **Transport OK; radio not appearing** |

---

## Package Catalog

### 1. Base Driver_Qualcomm_0.7700.1 (Acer OEM)
**Source:** Acer support page download — the primary Qualcomm platform package  
**Local path:** `C:\Users\user\Desktop\Base Driver_Qualcomm_0.7700.1_W11ARM64_A\Base Driver_Qualcomm_0.7700.1_W11ARM64_(Qualcomm Base Driver)\`  
**Also extracted to:** `driver-packages\extracted\Base_Driver_Qualcomm_0.7700.1_W11ARM64_A\`  
**WARNING:** Never run `Setup_Driver.cmd` from this package. Caused BSOD twice. Install INFs one at a time only.

| INF File | Version | Hardware ID(s) — A14 relevant | Purpose | Install Status |
|---|---|---|---|---|
| `HalExtQCWdogTimer8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C04` | Watchdog timer HAL extension | Unknown |
| `qcabd.inf` | 1.0.4160.6000 | `ACPI\QCOM0427` | Acer base driver shim | Unknown |
| `qcacsp_crd8380.inf` | 1.0.4160.6000 | (no ACPI HW IDs) | ACSP configuration extension | Unknown |
| `qcadc8380.inf` | (missing ver) | `ACPI\QCOM0C11` | Analog-to-Digital Converter | Installed — fails to start |
| `qcadcm8380.inf` | 1.0.4157.4500 | (none) | ADC monitor | Unknown |
| `qcadsprpc8380.inf` | 1.0.4196.6900 | `ACPI\QCOM0C5C` | ADSP RPC | Unknown |
| `qcadsprpcd8380.inf` | 1.0.4196.6900 | `ACPI\QCOM0C82` | ADSP RPC daemon | Unknown |
| `qcAlwaysOnSensing.inf` | 4675.1258.0.0 | `ACPI\QCOM0D06` | Always-on sensing | Unknown |
| `qcasd*.inf` / `qcaucd*.inf` / `qcaudminiport*.inf` | 1.0.4166.1200 | (none) | Audio service driver / audio codec | Blocked by ADSP |
| `qcbattminiclass8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C2A` | Battery mini class | Unknown |
| `qcbluetooth8380.inf` | 1.0.4216.6600 | `ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CRD08380` | **Bluetooth radio — CRD08380 match!** | Not installed |
| `qcbluetooth_nvm_ext8380.inf` | 1.0.4216.6600 | `ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CLS/MTP/QRD` | Bluetooth NVM extension | Not installed (no CRD match) |
| `qcbluetooth_swiftpair_ext8380.inf` | 1.0.4216.6600 | `ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CLS/MTP/QRD` | Bluetooth Swift Pair ext | Not installed (no CRD match) |
| `qcbtacx_transportdriver8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0D04` | BT ACX transport — **already OK** | Installed — OK |
| `qcbtaddvscregistry8380.inf` | 1.0.4216.6600 | (none) | BT registry component | Unknown |
| `qccdi8380.inf` | 1.0.4216.6600 | `ACPI\QCOM0C2F` | CDI (CDSP interface) | Unknown |
| `qcconnectionsecurity8380.inf` | 1.0.4166.1200 | `ACPI\QCOM0CA8` | Connection Security Device | **Installed — OK (Session 8)** |
| `qcDCF.inf` | 1.0.4160.6000 | `ACPI\QCOM06E7` | DCF device | Unknown |
| `QCDiagBridge.inf` | 1.0.4160.6000 | `ACPI\QCOM06DE` | Diag bridge | Unknown |
| `qcdiagrouter8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C13` | Diag router | Unknown |
| `qcdpps8380.inf` | 1.0.4227.8600 | `ACPI\VEN_QCOM&DEV_0C36`, `ACPI\VEN_QCOM&DEV_0D17` | Display port power switch / **Adreno GPU** | Not installed — QCOM0D17 = Adreno |
| `qcdxext_qcdpps8380.inf` | 1.0.4227.8600 | `ACPI\VEN_QCOM&DEV_0C36`, `ACPI\VEN_QCOM&DEV_0D17` | DX extension for above | Not installed |
| `qcfgbcl8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C77` | FG BCL device | Unknown |
| `qcfgbclext8380.inf` | 1.0.4160.6000 | `ACPI\VEN_QCOM&DEV_0C77&SUBSYS_CRD08380` | FG BCL extension | Unknown |
| `qcglink8380.inf` | 1.0.4219.5800 | `ACPI\QCOM0C84` | GLINK — **already running** | Installed — OK |
| `qcgpi8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C88` | GPI (General Purpose Interface) | Unknown |
| `qcgpio8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C0C` | GPIO | Unknown |
| `qcHumanPresenceSensor.inf` | 1.0.4160.6000 | `ACPI\QCOM06D9` | Human Presence Sensor (HPS) | Installed — WUDFRd fails |
| `qchwnled8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C68` | HW notification LED | Unknown |
| `qci2c8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C10` | I2C bus | Unknown |
| `qciommu.inf` | 1.0.4160.6000 | `ACPI\QCOM0200`, `ACPI\QCOM068F` | IOMMU | Unknown |
| `qciommuext8380.inf` | 1.0.4160.6000 | `ACPI\VEN_QCOM&DEV_068F&SUBSYS_CRD08380` | IOMMU extension | Unknown |
| `qcipcc8380.inf` | 1.0.4160.6000 | `ACPI\QCOM02FA`, `ACPI\QCOM06C2` | IPCC — **already running** | Installed — OK |
| `qcipcrouter8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C0D` | IPC Router — **already running** | Installed — OK |
| `qckmbam8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C0A` | KMBAM | Unknown |
| `QCListenSM*.inf` | 1.0.4160.6000 | (none) | ListenSM audio | Blocked by ADSP |
| `qcnspmcdm_ext_cdsp8380.inf` | 30.0.0140.1000 | `ACPI\VEN_QCOM&DEV_06DF` | NSP MCM CDSP extension | Likely staged/not bound |
| `qcnspmcdm8380.inf` | 30.0.0140.1000 | `ACPI\VEN_QCOM&DEV_0D0A` | NSP MCM modem | Unknown |
| `qcpdsr.inf` | 1.0.4160.6000 | `ACPI\QCOM06DF` | PDSR | Unknown |
| `qcpep.wd8380.inf` | 1.0.4196.6900 | `ACPI\QCOM0C17`, `ACPI\QCOM0C37`, `ACPI\QCOM0C38` | PEP (Power Engine Plugin) core | **WOA version (oem89.inf) used instead — newer** |
| `qcpil.inf` | 1.0.4216.6600 | `ACPI\QCOM06E0` | PIL core | **WOA version (oem95.inf) used — running OK** |
| `qcpilEXT8380.inf` | 2.0.4219.5800 | `ACPI\VEN_QCOM&DEV_06E0&SUBSYS_CRD08380` | PIL extension for CRD | Staged — cleared from failing list |
| `qcpilfilterext.inf` | 1.0.4216.6600 | `ACPI\QCOM06E0` | PIL filter extension — **running OK** | Installed — OK |
| `qcpmic8380.inf` | 1.0.4166.1200 | `ACPI\QCOM0C2B`, `ACPI\QCOM0CD3` | PMIC | Unknown |
| `QcPmicApps8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C2C` | PMIC Apps — **already running** | WOA version staged/running |
| `qcpmicext8380.inf` | 1.0.4166.1200 | `ACPI\VEN_QCOM&DEV_0CD3` | PMIC extension | Unknown |
| `QcPmicGlink8380.inf` | 1.0.4175.2700 | `ACPI\QCOM0C8E` | PMIC GLink — **already running** | WOA version staged/running |
| `qcpmicgpio8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C2D` | PMIC GPIO | Unknown |
| `qcppx8380.inf` | 1.0.4275.5000 | `ACPI\QCOM0C96` | PPX device | Unknown |
| `qcRng8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C85` | Random Number Generator | **Installed — OK (Session 9, oem81.inf)** |
| `qcrpen.inf` | 1.0.4160.6000 | `ACPI\QCOM06E1` | RPEN device | **Installed — OK (Session 9, oem78.inf)** |
| `qcscm.inf` | 1.0.4160.6000 | `ACPI\QCOM04DD` | Secure Channel Manager — **running** | **Installed (Session 10, oem84.inf)** |
| `qcsecapp.inf` | 1.0.4166.1200 | `ACPI\QCOM0CE4` | Secure App | **Installed — OK (Session 9, oem83.inf)** |
| `qcSensors.inf` | 1.0.4160.6000 | `ACPI\QCOM0CE7` | Sensors hub | Unknown |
| `qcSensorsConfigCrd8380.inf` | 4590.937.0.0 | `ACPI\VEN_QCOM&DEV_0693&SUBSYS_CRD08380` | Sensor config for CRD | Unknown |
| `qcshutdownsvc.inf` | 1.0.4160.6000 | `ACPI\QCOM06DB` | Shutdown service | Unknown |
| `QcSkExt8380.inf` | 1.0.4222.9100 | `ACPI\QCOM0CAC` | SK extension | **Installed (Session 10, oem86.inf)** |
| `qcslimbus8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0190` | SLIMbus | Unknown |
| `qcsmmu8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0200`, `ACPI\QCOM0C09` | SMMU — **running** | Staged (Session 13) — OK |
| `QcSOCPartition.inf` | 1.0.4160.6000 | `ACPI\QCOM06DD` | SoC Partition — **running** | **Installed (Session 10, oem85.inf)** |
| `QcSocServiceKMDF8380.inf` | 1.0.4196.6900 | `ACPI\QCOM0D18` | SoC Service KMDF | **Installed (Session 10, oem87.inf)** |
| `qcsp8380.inf` | 1.0.4196.6900 | `ACPI\QCOM0307`, `ACPI\QCOM0492`, **`ACPI\QCOM0C87`** | **Secure Platform Device — key SSDT target** | Staged oem102.inf — not bound (needs SSDT) |
| `qcspi8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C0E` | SPI bus | Unknown |
| `qcspmi8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C0B` | SPMI bus | Unknown |
| `qcSSGServicesUMD.inf` | 1.0.4160.6000 | `ACPI\QCOM06D8` | SSG Services UMD | **Installed — OK (Session 9, oem77.inf)** |
| `qcsubsys_ext_cdsp8380.inf` | 2.0.4219.5800 | `ACPI\VEN_QCOM&DEV_0CB0&SUBSYS_CRD08380` | Subsystem ext for CDSP | Staged — likely bound |
| `qcsubsys_ext_spss8380.inf` | 2.0.4219.5800 | `ACPI\VEN_QCOM&DEV_0C8D&SUBSYS_CRD08380` | Subsystem ext for SPSS | Staged — likely bound |
| `qcsubsys8380.inf` | 2.0.4219.5800 | `ACPI\QCOM0C1B` (ADSP), `ACPI\QCOM0C8D` (SPSS), `ACPI\QCOM0C20` (SSDD) | Subsystem driver — **all bound, ADSP/CDSP/SPSS fail at runtime** | Installed — oem70.inf |
| `qcSubsysThermalMgr.inf` | 1.0.4160.6000 | `ACPI\QCOM06E5`, `ACPI\QCOMFFE0` | Subsystem Thermal Manager | **Installed (Session 10, oem88.inf) — fails AddDevice** |
| `qcsyscache8380.inf` | 1.0.4196.6900 | `ACPI\QCOM0200`, `ACPI\QCOM0C83` | System cache — **running** | Staged (Session 13) — OK |
| `QcTftpKmdf.inf` | 1.0.4160.6000 | `ACPI\QCOM06DC` | TFTP KMDF — **running** | WOA version staged (Session 13) — OK |
| `QcTrEE.inf` | 1.0.4160.6000 | `ACPI\QCOM04DE` | TrEE (Trusted Execution Environment) — **running** | WOA version oem99.inf |
| `QcTreeExtOem8380.inf` | 1.0.4166.1200 | `ACPI\VEN_QCOM&DEV_04DE&SUBSYS_CRD08380` | TrEE OEM extension | WOA version oem100.inf |
| `QcTreeExtQcom8380.inf` | 1.0.4166.1200 | `ACPI\VEN_QCOM&DEV_04DE&SUBSYS_CRD08380` | TrEE Qualcomm extension | WOA version oem101.inf |
| `qcuart8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C16` | UART / Bus Device | **Installed oem79.inf — fails AddDevice** |
| `qcursext.inf` | 1.0.4160.6000 | `ACPI\QCOMFFE1` | URS extension | Unknown |
| `QcUsb4Bus8380.inf` | 1.0.4160.6000 | `ACPI\QCOM0C6D` | USB4 bus | **Installed — OK (Session 9, oem80.inf)** |
| `QcUsb4Filter8380.inf` | 1.0.4196.6900 | (no ACPI HW IDs) | USB4 filter | Unknown |
| `qcusbcucsi8380.inf` | 4794.346.0.0 | `ACPI\QCOM0CA4` | USB-C UCSI | Unknown |
| `QcUsbFnSsFilter8380.inf` | 1.0.4160.6000 | (none) | USB function SS filter | Unknown |
| `qcwlanhmt*.inf` / `qcwlanhsp*.inf` / `qcwlanmsl*.inf` | 1.0.4216.6600 | `ACPI\VEN_QCOM&DEV_0CD5&SUBSYS_CRD08380` | Wi-Fi HMT/HSP/MSL — WiFi working | Installed — OK |
| `qcwlanmsl_ext_wpss8380.inf` | 1.0.4166.1200 | `ACPI\VEN_QCOM&DEV_06DF&SUBSYS_CRD08380` | WPSS ext | Staged |
| `qcwwanpowerdown.inf` | 1.0.4160.6000 | `ACPI\QCOM0CDA` | WWAN power down | **Installed — OK (Session 9, oem82.inf)** |
| `QcXhciFilter8380.inf` | 1.0.4219.5800 | `ACPI\QCOM0CA1`, `ACPI\QCOM0D08`, `ACPI\QCOM0D09` | xHCI filter | Unknown |
| `qsarconfig8380.inf` / `qSarMgr.inf` | 1.0.4160.6000 | `ACPI\VEN_QCOM&DEV_06E2&SUBSYS_CRD08380` | SAR manager | Unknown |
| `ufnserialcomposite.inf` | 1.0.4160.6000 | (none) | USB function serial composite | Unknown |

---

### 2. Base Driver_Qualcomm_31.0.112.0 (Qualcomm Multimedia)
**Source:** Acer support page — mislabeled as "base driver"; actually Qualcomm Multimedia (camera, DX, EVA)  
**Local path:** `driver-packages\extracted\Base_Driver_Qualcomm_31.0.112.0_W11ARM64_A\`  
**Install status:** Installed (Session 1 era)

| INF File | Purpose | Key HW IDs |
|---|---|---|
| Camera/DX/EVA related INFs (24 total) | DirectX, camera sensors, EVA | Various camera and display IDs |

---

### 3. ADSP_Qualcomm_2.0.8100.0002 (Qualcomm ADSP firmware extension)
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\ADSP_Qualcomm_2.0.8100.0002_W11ARM64_A\`  
**Install status:** Installed (referenced in Session table)

| INF File | Version | Key HW IDs (A14 relevant) |
|---|---|---|
| `qcsubsys_ext_adsp8380.inf` | 2.0.8100.0002 (2025-09-08) | `ACPI\VEN_QCOM&DEV_06E0&SUBSYS_CRD08380`, `ACPI\VEN_QCOM&DEV_06DF&SUBSYS_CRD08380`, `ACPI\VEN_QCOM&DEV_0C1B&SUBSYS_CRD08380` |

**Note:** This is the ADSP subsystem extension — newer than the 0.7700.1 version. Already installed.

---

### 4. APP Base driver_Acer_1.0.0.4 (Acer Application Base)
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\APP_Base_driver_Acer_1.0.0.4_W11ARM64_A\`  
**Install status:** Installed

| INF File | Version | HW IDs |
|---|---|---|
| `AcerApplicationBaseDriver.inf` | 1.0.0.4 | `ACPI\VEN_1025&DEV_165F`, `ACPI\VEN_1025&DEV_1783` |

---

### 5. Audio Console_Acer_0.6.7.0
**Source:** Acer support page  
**Install status:** Installed  
**Note:** App-layer audio console. Not a kernel driver. Contains no INFs with ACPI HW IDs.

---

### 6. Camera_Microsoft_2.0.13
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\Camera_Microsoft_2.0.13_W11ARM64_A\`  
**Install status:** Installed

| INF File | Version | Notes |
|---|---|---|
| `mep_audio_component.inf` | 2.0.13.0 | MEP audio |
| `mep_camera_component.inf` | 2.0.13.0 | MEP camera |
| `MicrosoftEffectPack_extension.inf` | 2.0.13.0 | `ACPI\QCOMFFE9` — camera effect extension |

---

### 7. Camera_Morpho_2.1.11.0
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\Camera_Morpho_2.1.11.0_W11ARM64_A\`  
**Install status:** Installed

| INF File | Version | Notes |
|---|---|---|
| `mordmft.inf` | 2.1.11.0 | Morpho camera ISP MFT — no ACPI HW IDs |

---

### 8. CardReader_Realtek_10.0.26100.31287
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\CardReader_Realtek_10.0.26100.31287_W11ARM64_A\`  
**Install status:** Installed — OK

| INF File | Version | Notes |
|---|---|---|
| `RtsUer.inf` | 10.0.26100.31287 | Realtek USB card reader — no ACPI HW IDs |

---

### 9. DES Driver_Acer_1.0.0.3018
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\DES_Driver_Acer_1.0.0.3018_W11ARM64_A\`  
**Install status:** Installed

| INF File | Version | HW IDs |
|---|---|---|
| `AcerDeviceEnablingServiceComponent.inf` | 1.0.0.3018 | (none — component layer) |
| `AcerDeviceEnablingServiceExtension.inf` | 1.0.0.3012 | `ACPI\VEN_1025&DEV_165F&SUBSYS_100[123]1025` |

---

### 10. ESS Security_Microsoft_1.0.0.241030
**Source:** Acer support page  
**Install status:** Not needed for driver recovery  
**Note:** This package contains only `SecureBiometricsREG.cmd` which enables VBS Secure Biometrics (`HKLM\...\DeviceGuard\Scenarios\SecureBiometrics /v Enabled`). It is not a driver and has no relation to the Qualcomm platform stack. Safe to run but irrelevant to the current failure set.

---

### 11. Keyboard_Acer_1.0.0.5
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\Keyboard_Acer_1.0.0.5_W11ARM64_A\`  
**Install status:** Installed — OK

| INF File | Version | HW IDs |
|---|---|---|
| `CExtensionDrv.inf` | 1.0.0.5 | `ACPI\VEN_1025&DEV_165F&SUBSYS_1203/12041025` — Acer keyboard extension |
| `CSWComponentDrv.inf` | 1.0.0.5 | (none — component) |

---

### 12. Shipping Document_Acer_1.0
**Source:** Acer support page  
**Note:** Contains only a PDF/documentation. No drivers.

---

### 13. XPERI DTS_XPERI_2.0.5.0
**Source:** Acer support page  
**Local path:** `driver-packages\extracted\XPERI_DTS_XPERI_2.0.5.0_W11ARM64_A\`  
**Install status:** Installed (audio console layer — blocked until ADSP works)

| INF File | Version | Notes |
|---|---|---|
| `dtsapo5Arm64.inf` | 2.5.3.0 | DTS APO ARM64 audio effects |
| `dtsapo5ultraAcerextensionpkg.inf` | 2.0.5.0 | Acer-specific DTS extension |
| `DtsHubService.inf` | 2025.2.2.0 | DTS hub service |
| `subhsa.inf` | 2025.1.12.0 | Sub-HSA component |
| `ultra2hsa.inf` | 2.2.1.0 | Ultra2 HSA component |

---

## WOA-Project Drivers Staged / Installed

**Source repo:** `WOA-Project/Qualcomm-Reference-Drivers`  
**Driver folder:** `https://github.com/WOA-Project/Qualcomm-Reference-Drivers/tree/master/8380_CRD/200.0.57.0`  
**Raw CAB pattern:** `https://github.com/WOA-Project/Qualcomm-Reference-Drivers/raw/master/8380_CRD/200.0.57.0/<name>.cab`  
**Local extraction root:** `C:\Drivers\`

| CAB Name | Published INF | Version | Hardware ID | Current Status |
|---|---|---|---|---|
| `qcconnectionsecurity8380.cab` | oem46.inf | 1.0.4166.1200 | `ACPI\QCOM0CA8` | **Installed — OK (Session 8)** |
| `qcpep.wd8380.cab` | oem89.inf | 1.0.4478.2200 | `ACPI\QCOM0C17`, etc. | Staged — qcpep stopped (blocked) |
| `QcPmicApps8380.cab` | staged | 1.0.4478.2200 | `ACPI\QCOM0C2C` | **Staged — now running (Session 13)** |
| `QcPmicGlink8380.cab` | staged | 1.0.4478.2200 | `ACPI\QCOM0C8E` | **Staged — now running (Session 13)** |
| `QcTftpKmdf.cab` | staged | 1.0.4478.2200 | `ACPI\QCOM06DC` | **Staged — now running (Session 13)** |
| `qcpil.cab` | oem95.inf | 1.0.4478.2200 | `ACPI\QCOM06E0` | **Staged + running — PIL OK (Session 14)** |
| `qcpilEXT8380.cab` | staged | 1.0.4478.2200 | `ACPI\VEN_QCOM&DEV_06E0&SUBSYS_CRD08380` | Staged (Session 14) |
| `qcpilfilterext.cab` | staged | 1.0.4478.2200 | `ACPI\QCOM06E0` | **Staged + running — PIL filter OK** |
| `QcTrEE.cab` | oem99.inf | 1.0.4478.2200 | `ACPI\QCOM04DE` | Staged (Session 15) — device was already OK |
| `QcTreeExtOem8380.cab` | oem100.inf | 1.0.4478.2200 | `ACPI\VEN_QCOM&DEV_04DE&SUBSYS_CRD08380` | Staged (Session 15) |
| `QcTreeExtQcom8380.cab` | oem101.inf | 1.0.4478.2200 | `ACPI\VEN_QCOM&DEV_04DE&SUBSYS_CRD08380` | Staged (Session 15) |
| `qcsp8380.cab` | oem103.inf | 1.0.4478.2200 | **`ACPI\QCOM0C87`** | **Staged (Session 15) — needs SSDT to bind** |

---

## Hardware ID Cross-Reference (Failing → INF)

| ACPI Hardware ID | Device Name | Matched INF | Package | Status |
|---|---|---|---|---|
| `ACPI\QCOM0C87` | Secure Platform Device (QCSP) | `qcsp8380.inf` | Base 0.7700.1 + WOA | Staged, needs SSDT injection |
| `ACPI\QCOM0C1B` | ADSP | `qcsubsys8380.inf` | Base 0.7700.1 | Installed, runtime fail |
| `ACPI\QCOM0CB0` | CDSP | `qcsubsys8380.inf` | Base 0.7700.1 | Installed, runtime fail |
| `ACPI\QCOM0C8D` | SPSS | `qcsubsys8380.inf` | Base 0.7700.1 | Installed, runtime fail |
| `ACPI\QCOM0C5A`, `0C58`, `0C59`, `0CBF`, `0C91`, `0D05` | Temp Sensors / Fan EC | `qcpep.wd8380.inf` | WOA oem89.inf | Staged, qcpep stopped |
| `ACPI\VEN_QCOM&DEV_0CF2–0CFC` | Policy Devices | `qcpep.wd8380.inf` | WOA oem89.inf | Staged, qcpep stopped |
| `ACPI\QCOM0C11` | ADC | `qcadc8380.inf` | Base 0.7700.1 | Installed, fails to start |
| `ACPI\QCOM0C16` | UART Bus Device | `qcuart8380.inf` | Base 0.7700.1 oem79.inf | Installed, fails AddDevice |
| `ACPI\QCOM06D9` | Human Presence Sensor | `qcHumanPresenceSensor.inf` | Base 0.7700.1 oem35.inf | Installed, WUDFRd fails |
| `ACPI\QCOM0CD5` | Subsys Thermal Mgr | `qcSubsysThermalMgr.inf` | Base 0.7700.1 oem88.inf | Installed, fails AddDevice |
| `ACPI\VEN_QCOM&DEV_0D17` | Adreno GPU | `qcdpps8380.inf` | Base 0.7700.1 | Not installed — needs investigation |
| `ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CRD08380` | Bluetooth radio | `qcbluetooth8380.inf` | Base 0.7700.1 | **Not installed — candidate for next session** |
| `ACPI\QCOM0CF1` | EVA Device | `qcdpps8380.inf` / `qcdxext_qcdpps8380.inf` | Base 0.7700.1 | Not installed — needs investigation |
| `ACPI\QCOM0C32\1B` | ISP Camera Platform | No confident match found | — | Unknown — needs `Get-PnpDeviceProperty` investigation |

---

## Key File Locations on This Machine

| Item | Path |
|---|---|
| DSDT binary (extracted) | `C:\Drivers\dsdt.aml` |
| SSDT ASL source | `C:\Drivers\ssdt_qcsp.asl` — recreated in May 2026 (was only on a separate working machine before then) |
| SSDT AML compiled (after iasl run) | `C:\Drivers\ssdt_qcsp.aml` — **not yet created, needs iasl** |
| `iasl.exe` compiler | `C:\Drivers\iasl.exe` — **NOT YET DOWNLOADED — next action** |
| WOA qcsp8380 extracted | `C:\Drivers\WOA_qcsp8380\` |
| WOA TrEE packages | `C:\Drivers\WOA_TrEE\` |
| WOA PIL packages | `C:\Drivers\WOA_8380_Phase4_PIL\` |
| WOA PMIC/TFTP packages | `C:\Drivers\WOA_8380_Phase2\` |
| WOA QCPEP extracted | `C:\Drivers\WOA_qcpep8380\` |
| Acer base driver package | `C:\Users\user\Desktop\Base Driver_Qualcomm_0.7700.1_W11ARM64_A\` |
| Driver package ZIPs | `C:\Users\user\Desktop\A14\driver-packages\` |
| Driver package extracted | `C:\Users\user\Desktop\A14\driver-packages\extracted\` |
| Baseline CSVs + logs | `C:\Users\user\Desktop\A14\baselines\` |
| Diagnostic ZIP captures | `C:\Users\user\Desktop\A14\diagnostic-captures\` |
| Full driver INF catalog CSV | `C:\Users\user\Desktop\A14\baselines\Driver_Package_Map_20260526_130845.csv` |

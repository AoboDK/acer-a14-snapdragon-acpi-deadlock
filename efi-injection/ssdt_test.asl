// Canary SSDT — used to verify injection paths before deploying the real QCSP fix.
// Creates a stub device with HID "QCOM1234" and no _DEP at \_SB.TST0.
// If injection succeeds, ACPI\QCOM1234\0 appears in Device Manager.
// See: scripts/update_acpitables.ps1, scripts/esp_test.bat

DefinitionBlock ("ssdt_test.aml", "SSDT", 2, "QCOMM_", "TSTDEV1", 0x00000001)
{
    Scope (_SB)
    {
        Device (TST0)
        {
            Name (_HID, "QCOM1234")
            Name (_UID, 0x42)
            Method (_STA, 0, NotSerialized) { Return (0x0F) }
        }
    }
}

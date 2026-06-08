DefinitionBlock ("ssdt_qcsp.aml", "SSDT", 2, "QCOMM_", "QCSP87", 0x00000001)
{
    Scope (_SB)
    {
        Device (QSP0)
        {
            Name (_HID, "QCOM0C87")
            Name (_UID, One)
            Method (_STA, 0, NotSerialized)
            {
                Return (0x0F)
            }
        }
    }
}

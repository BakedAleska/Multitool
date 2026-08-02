<#
.SYNOPSIS
Autoclicker backend for Windows. Prints a JSON status line to stdout after
each click, until the process is terminated by its parent.

.PARAMETER IntervalMs
Milliseconds to wait between clicks.

.PARAMETER Button
Which mouse button to click: "left" or "right".

.PARAMETER DryRun
Skip the actual click, still print status lines. Used for testing this
script's protocol without generating real input.
#>
param(
    [double]$IntervalMs = 100,
    [string]$Button = "left",
    [switch]$DryRun
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class MouseSimulator {
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, UIntPtr dwExtraInfo);

    public const uint MOUSEEVENTF_LEFTDOWN = 0x02;
    public const uint MOUSEEVENTF_LEFTUP = 0x04;
    public const uint MOUSEEVENTF_RIGHTDOWN = 0x08;
    public const uint MOUSEEVENTF_RIGHTUP = 0x10;
}
"@

$downFlag = if ($Button -eq "right") { [MouseSimulator]::MOUSEEVENTF_RIGHTDOWN } else { [MouseSimulator]::MOUSEEVENTF_LEFTDOWN }
$upFlag = if ($Button -eq "right") { [MouseSimulator]::MOUSEEVENTF_RIGHTUP } else { [MouseSimulator]::MOUSEEVENTF_LEFTUP }

$count = 0
while ($true) {
    if (-not $DryRun) {
        [MouseSimulator]::mouse_event($downFlag, 0, 0, 0, [UIntPtr]::Zero)
        [MouseSimulator]::mouse_event($upFlag, 0, 0, 0, [UIntPtr]::Zero)
    }
    $count++
    [Console]::Out.WriteLine((@{ count = $count } | ConvertTo-Json -Compress))
    [Console]::Out.Flush()
    Start-Sleep -Milliseconds $IntervalMs
}

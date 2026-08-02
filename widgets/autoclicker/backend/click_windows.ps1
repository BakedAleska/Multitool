<#
.SYNOPSIS
Autoclicker backend for Windows. Prints a JSON status line to stdout after
each click, until the process is terminated by its parent.

.PARAMETER IntervalMs
Milliseconds to wait between clicks. Computed by widget.py from a
clicks-per-second value, not entered directly.

.PARAMETER Button
Which mouse button to click: "left", "right", or "middle".

.PARAMETER RandomizePercent
If greater than 0, each click's wait is jittered by up to this percent
in either direction, so the click pattern isn't perfectly periodic.

.PARAMETER DryRun
Skip the actual click, still print status lines. Used for testing this
script's protocol without generating real input.
#>
param(
    [double]$IntervalMs = 100,
    [string]$Button = "left",
    [double]$RandomizePercent = 0,
    [switch]$DryRun
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class MouseSimulator {
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, UIntPtr dwExtraInfo);

    [DllImport("winmm.dll")]
    public static extern uint timeBeginPeriod(uint uPeriod);

    public const uint MOUSEEVENTF_LEFTDOWN = 0x02;
    public const uint MOUSEEVENTF_LEFTUP = 0x04;
    public const uint MOUSEEVENTF_RIGHTDOWN = 0x08;
    public const uint MOUSEEVENTF_RIGHTUP = 0x10;
    public const uint MOUSEEVENTF_MIDDLEDOWN = 0x20;
    public const uint MOUSEEVENTF_MIDDLEUP = 0x40;
}
"@

# Windows' default scheduler tick is ~15.6ms, which makes Start-Sleep
# coarse and unreliable for the short waits high-CPS clicking needs.
# Asking for 1ms resolution here (undone automatically when this process
# exits) is what lets the CPS bounds enforced in widget.py actually hold.
[MouseSimulator]::timeBeginPeriod(1) | Out-Null

$downFlag = switch ($Button) {
    "right" { [MouseSimulator]::MOUSEEVENTF_RIGHTDOWN }
    "middle" { [MouseSimulator]::MOUSEEVENTF_MIDDLEDOWN }
    default { [MouseSimulator]::MOUSEEVENTF_LEFTDOWN }
}
$upFlag = switch ($Button) {
    "right" { [MouseSimulator]::MOUSEEVENTF_RIGHTUP }
    "middle" { [MouseSimulator]::MOUSEEVENTF_MIDDLEUP }
    default { [MouseSimulator]::MOUSEEVENTF_LEFTUP }
}

$random = New-Object System.Random
$count = 0
while ($true) {
    if (-not $DryRun) {
        [MouseSimulator]::mouse_event($downFlag, 0, 0, 0, [UIntPtr]::Zero)
        [MouseSimulator]::mouse_event($upFlag, 0, 0, 0, [UIntPtr]::Zero)
    }
    $count++
    [Console]::Out.WriteLine((@{ count = $count } | ConvertTo-Json -Compress))
    [Console]::Out.Flush()

    $wait = $IntervalMs
    if ($RandomizePercent -gt 0) {
        $deviation = $IntervalMs * ($RandomizePercent / 100)
        $wait = $IntervalMs + (($random.NextDouble() * 2 - 1) * $deviation)
        if ($wait -lt 1) { $wait = 1 }
    }
    Start-Sleep -Milliseconds $wait
}

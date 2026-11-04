param(
    [switch]$SelfTest,
    [int]$HoldSeconds = 0
)

# 护屏遮罩：铺满全屏的纯黑无边框窗口。
# OLED 屏黑色像素不发光 => 视觉上等同熄屏，但系统不进待机、不断网、任务照跑。
# 任意按键 / 点击 / 大幅移动鼠标 => 退出。

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type -Namespace Win32 -Name Power -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

$ES_CONTINUOUS       = 0x80000000L
$ES_SYSTEM_REQUIRED  = 0x00000001L
$ES_DISPLAY_REQUIRED = 0x00000002L
$script:keepAwake    = [uint32]((($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED)) -band 0xFFFFFFFFL)
$script:releaseFlags = [uint32](($ES_CONTINUOUS) -band 0xFFFFFFFFL)

# 1) 挂住系统与显示器的空闲计时器，防止关屏/待机
$script:reqResult = [Win32.Power]::SetThreadExecutionState($script:keepAwake)

$script:startCursor = [System.Windows.Forms.Cursor]::Position
$script:closed = $false

$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.StartPosition   = [System.Windows.Forms.FormStartPosition]::Manual
$form.Bounds          = [System.Windows.Forms.SystemInformation]::VirtualScreen
$form.BackColor       = [System.Drawing.Color]::Black
$form.TopMost         = $true
$form.ShowInTaskbar   = $false
$form.KeyPreview      = $true
$form.Cursor          = [System.Windows.Forms.Cursors]::Default

$hint = New-Object System.Windows.Forms.Label
$hint.AutoSize  = $false
$hint.Dock      = [System.Windows.Forms.DockStyle]::Fill
$hint.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$hint.ForeColor = [System.Drawing.Color]::FromArgb(85, 85, 85)
$hint.BackColor = [System.Drawing.Color]::Black
$hint.Font      = New-Object System.Drawing.Font('Microsoft YaHei UI', 14)
$hint.Text      = "护屏模式`r`n按任意键或移动鼠标退出"
$form.Controls.Add($hint)

function Close-Shield {
    if ($script:closed) { return }
    $script:closed = $true
    $form.Close()
}

$form.Add_KeyDown({ Close-Shield })
$form.Add_MouseDown({ Close-Shield })
$form.Add_MouseMove({
    $p = [System.Windows.Forms.Cursor]::Position
    $dx = [Math]::Abs($p.X - $script:startCursor.X)
    $dy = [Math]::Abs($p.Y - $script:startCursor.Y)
    if ($dx -gt 60 -or $dy -gt 60) { Close-Shield }
})

# 6 秒后淡出提示文字，留纯黑
$fadeTimer = New-Object System.Windows.Forms.Timer
$fadeTimer.Interval = 6000
$fadeTimer.Add_Tick({
    $hint.Visible = $false
    $fadeTimer.Stop()
})
$fadeTimer.Start()

$form.Add_Shown({ $form.Activate() })

if ($SelfTest) {
    $auto = New-Object System.Windows.Forms.Timer
    $auto.Interval = 2500
    $auto.Add_Tick({ Close-Shield })
    $auto.Start()
    Write-Output "selftest-window-open"
}

if ($HoldSeconds -gt 0) {
    $hold = New-Object System.Windows.Forms.Timer
    $hold.Interval = $HoldSeconds * 1000
    $hold.Add_Tick({ Close-Shield })
    $hold.Start()
}

[void]$form.ShowDialog()

# 收尾：释放唤醒锁
[void][Win32.Power]::SetThreadExecutionState($script:releaseFlags)
Write-Output "shield-closed"

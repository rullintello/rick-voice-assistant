# Shown by Run Rick.bat on the first start only: Rick needs Python, which
# the user installs from the official site. Ticking the box means "done":
# Run Rick.bat then remembers it and never shows this again.
# Exit code 0 = box ticked (go on with the setup), 1 = not yet.
# ASCII only on purpose: Windows PowerShell 5.1 misreads accents in a .ps1.

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$url = "https://www.python.org/downloads/"

$form = New-Object System.Windows.Forms.Form
$form.Text = "Rick - Serve Python / Python needed"
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.AutoSize = $true
$form.AutoSizeMode = "GrowAndShrink"
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$panel = New-Object System.Windows.Forms.FlowLayoutPanel
$panel.FlowDirection = "TopDown"
$panel.AutoSize = $true
$panel.WrapContents = $false
$panel.Padding = New-Object System.Windows.Forms.Padding(20)
$form.Controls.Add($panel)

$text = New-Object System.Windows.Forms.Label
$text.AutoSize = $true
$text.MaximumSize = New-Object System.Drawing.Size(520, 0)
$text.Text = "Per funzionare, Rick ha bisogno di Python (gratuito).`r`n" +
    "Rick needs Python (free) to work.`r`n`r`n" +
    "1. Scaricalo dal sito ufficiale (pulsante giallo ""Download Python"").`r`n" +
    "    Download it from the official site (yellow ""Download Python"" button).`r`n" +
    "2. Installalo. Se te lo chiede, spunta ""Add python.exe to PATH"".`r`n" +
    "    Install it. If asked, check ""Add python.exe to PATH"".`r`n" +
    "3. Spunta la casella qui sotto e premi OK.`r`n" +
    "    Tick the box below and press OK."
$panel.Controls.Add($text)

$link = New-Object System.Windows.Forms.LinkLabel
$link.AutoSize = $true
$link.Text = $url
$link.Margin = New-Object System.Windows.Forms.Padding(3, 12, 3, 12)
$link.Add_LinkClicked({ Start-Process $url })
$panel.Controls.Add($link)

$check = New-Object System.Windows.Forms.CheckBox
$check.AutoSize = $true
$check.Text = "Ho scaricato e installato Python / I've downloaded and installed Python"
$panel.Controls.Add($check)

$ok = New-Object System.Windows.Forms.Button
$ok.Text = "OK"
$ok.AutoSize = $true
$ok.Margin = New-Object System.Windows.Forms.Padding(3, 16, 3, 3)
$ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
$panel.Controls.Add($ok)
$form.AcceptButton = $ok

[void]$form.ShowDialog()
if ($check.Checked) { exit 0 } else { exit 1 }

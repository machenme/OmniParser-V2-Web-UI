param(
    [string]$InputPath,
    [switch]$CopyToClipboard,
    [string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'output\latest.png')
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

if ($InputPath) {
    $image = [System.Drawing.Image]::FromFile((Resolve-Path -LiteralPath $InputPath).Path)
} else {
    $image = [System.Windows.Forms.Clipboard]::GetImage()
    if ($null -eq $image) { throw '剪贴板中没有图片，请先截图并复制。' }
}
$stream = New-Object System.IO.MemoryStream
try {
    $image.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $body = @{ image_base64 = [Convert]::ToBase64String($stream.ToArray()) } | ConvertTo-Json -Compress
} finally {
    $stream.Dispose()
    $image.Dispose()
}
try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:17897/parse/' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 180
} catch {
    throw '识别服务未响应（http://127.0.0.1:17897）。请先运行 Start.cmd 启动服务。'
}
[System.IO.File]::WriteAllBytes($OutputPath, [Convert]::FromBase64String($response.image_base64))
if ((-not $InputPath) -or $CopyToClipboard) {
    $marked = [System.Drawing.Image]::FromFile($OutputPath)
    try { [System.Windows.Forms.Clipboard]::SetImage($marked) } finally { $marked.Dispose() }
}
Write-Output ('已识别 {0} 个元素，耗时 {1} 秒。图片：{2}' -f $response.elements.Count, $response.seconds, $OutputPath)

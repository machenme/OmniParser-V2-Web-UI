$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $root 'Start.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors.Message -join "`n") }
$definition = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.StringConstantExpressionAst] -and $node.Value.Contains('public static class ScreenshotProcessJob') }, $true).Value
$python = Join-Path $root '.venv\Scripts\python.exe'
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ('ocr-lifetime-' + [Guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($temporary) | Out-Null
$fixture = Join-Path $temporary 'worker.py'
[System.IO.File]::WriteAllText($fixture, "import os, time`nfrom pathlib import Path`nPath(__file__).with_suffix('.pid').write_text(str(os.getpid()))`nprint('worker ready', flush=True)`ntime.sleep(120)`n")
$definition64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($definition))
$fixture64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($fixture))
$python64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($python))
try {
    foreach ($mode in @('close', 'exit', 'terminate')) {
        $pidFile = Join-Path $temporary 'worker.pid'
        if (Test-Path $pidFile) { Remove-Item -LiteralPath $pidFile -Confirm:$false }
        $childCode = @'
$ErrorActionPreference = 'Stop'
$definition = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__DEFINITION__'))
$fixture = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__FIXTURE__'))
$python = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__PYTHON__'))
Add-Type -TypeDefinition $definition -ReferencedAssemblies System.Windows.Forms
[ScreenshotProcessJob]::Create()
$workerId = [ScreenshotProcessJob]::Start($python, $fixture, (Split-Path $fixture))
$pidFile = [System.IO.Path]::ChangeExtension($fixture, '.pid')
$deadline = [DateTime]::UtcNow.AddSeconds(15)
while (-not (Test-Path $pidFile) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 50 }
if (-not (Test-Path $pidFile)) { throw '测试 Python 启动超时。' }
[System.IO.File]::WriteAllText((Join-Path (Split-Path $fixture) 'launcher.pid'), [string]$workerId)
if ('__MODE__' -eq 'close') {
    [ScreenshotProcessJob]::Close()
    exit
}
if ('__MODE__' -eq 'exit') { exit }
Start-Sleep -Seconds 120
'@
        $childCode = $childCode.Replace('__DEFINITION__', $definition64).Replace('__FIXTURE__', $fixture64).Replace('__PYTHON__', $python64).Replace('__MODE__', $mode)
        $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($childCode))
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = 'powershell.exe'
        $start.Arguments = "-NoProfile -NonInteractive -EncodedCommand $encoded"
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.RedirectStandardError = $true
        $hostProcess = [System.Diagnostics.Process]::Start($start)
        try {
            $launcherFile = Join-Path $temporary 'launcher.pid'
            $deadline = [DateTime]::UtcNow.AddSeconds(20)
            while (-not (Test-Path $pidFile) -and -not $hostProcess.HasExited -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 50 }
            if (-not (Test-Path $pidFile)) { throw ('测试启动失败：' + $hostProcess.StandardError.ReadToEnd()) }
            if ($mode -eq 'terminate') {
                while (-not (Test-Path $launcherFile) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 50 }
                if (-not (Test-Path $launcherFile)) { throw '测试宿主未就绪。' }
                $hostProcess.Kill()
            }
            if (-not $hostProcess.WaitForExit(10000)) { throw '测试宿主未退出。' }
            if ($mode -ne 'terminate' -and $hostProcess.ExitCode -ne 0) { throw $hostProcess.StandardError.ReadToEnd() }
            $workerId = [int][System.IO.File]::ReadAllText($pidFile)
            $launcherId = [int][System.IO.File]::ReadAllText($launcherFile)
            foreach ($processId in @($workerId, $launcherId)) {
                $remaining = Get-Process -Id $processId -ErrorAction SilentlyContinue
                if ($remaining -and -not $remaining.WaitForExit(5000)) { throw "Python 进程残留：$processId" }
            }
            $log = [System.IO.File]::ReadAllText((Join-Path $temporary 'logs\server.log'))
            if (-not $log.Contains('worker ready')) { throw '日志重定向失败。' }
            Write-Output "通过：$mode，虚拟环境启动器及实际 Python 均已结束，日志正常。"
        } finally {
            if (-not $hostProcess.HasExited) { $hostProcess.Kill(); $hostProcess.WaitForExit() }
            $hostProcess.Dispose()
            if (Test-Path (Join-Path $temporary 'launcher.pid')) { Remove-Item -LiteralPath (Join-Path $temporary 'launcher.pid') -Confirm:$false }
        }
    }
} finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force -Confirm:$false
}

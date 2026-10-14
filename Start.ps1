$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$url = 'http://127.0.0.1:17897'
$logs = Join-Path $PSScriptRoot 'logs'
[System.IO.Directory]::CreateDirectory($logs) | Out-Null
$logFile = Join-Path $logs 'startup-error.log'
function Write-StartupError($Stage, $Err) {
    $lines = @(
        ('[' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '] ' + $Stage),
        ('消息: ' + $Err.Exception.Message),
        ('位置: 行 ' + $Err.InvocationInfo.ScriptLineNumber + ' - ' + $Err.InvocationInfo.Line.Trim()),
        ('堆栈: ' + $Err.ScriptStackTrace)
    )
    $lines | Out-File $logFile -Append -Encoding utf8
    Write-Host ($lines -join "`r`n")
    try { [System.Windows.Forms.MessageBox]::Show(($lines -join "`r`n"), 'OmniParser V2 Web UI 启动失败') } catch { }
}
try {
Add-Type -TypeDefinition 'public class DpiAware { [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[DpiAware]::SetProcessDPIAware() | Out-Null
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;
public static class ScreenshotProcessJob {
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimits {
        public long ProcessTime, JobTime;
        public uint Flags;
        public UIntPtr MinimumWorkingSet, MaximumWorkingSet;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters {
        public ulong ReadOperations, WriteOperations, OtherOperations;
        public ulong ReadBytes, WriteBytes, OtherBytes;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimits {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimits limits, uint length);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);
    [StructLayout(LayoutKind.Sequential)]
    struct SecurityAttributes {
        public uint Length;
        public IntPtr Descriptor;
        public int Inherit;
    }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct StartupInfo {
        public uint Size;
        public string Reserved, Desktop, Title;
        public uint X, Y, XSize, YSize, XCount, YCount, Fill, Flags;
        public short ShowWindow, ReservedSize;
        public IntPtr ReservedData, Input, Output, Error;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct ProcessInfo {
        public IntPtr Process, Thread;
        public uint ProcessId, ThreadId;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFile(string path, uint access, uint share, ref SecurityAttributes attributes, uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcess(string application, System.Text.StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes, bool inherit, uint flags, IntPtr environment, string directory, ref StartupInfo startup, out ProcessInfo process);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll")]
    static extern bool TerminateProcess(IntPtr process, uint exitCode);
    static IntPtr job;
    public static void Create() {
        job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero)
            throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        ExtendedLimits limits = new ExtendedLimits();
        limits.Basic.Flags = 0x2000;
        if (!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(typeof(ExtendedLimits)))) {
            int error = Marshal.GetLastWin32Error();
            CloseHandle(job);
            job = IntPtr.Zero;
            throw new System.ComponentModel.Win32Exception(error);
        }
    }
    public static int Start(string executable, string script, string directory) {
        SecurityAttributes attributes = new SecurityAttributes();
        attributes.Length = (uint)Marshal.SizeOf(typeof(SecurityAttributes));
        attributes.Inherit = 1;
        IntPtr output = new IntPtr(-1), error = new IntPtr(-1), input = new IntPtr(-1);
        ProcessInfo process = new ProcessInfo();
        try {
            string logs = System.IO.Path.Combine(directory, "logs");
            System.IO.Directory.CreateDirectory(logs);
            output = CreateFile(System.IO.Path.Combine(logs, "server.log"), 0x40000000, 3, ref attributes, 2, 0x80, IntPtr.Zero);
            error = CreateFile(System.IO.Path.Combine(logs, "server-error.log"), 0x40000000, 3, ref attributes, 2, 0x80, IntPtr.Zero);
            input = CreateFile("NUL", 0x80000000, 3, ref attributes, 3, 0x80, IntPtr.Zero);
            if (output == new IntPtr(-1) || error == new IntPtr(-1) || input == new IntPtr(-1))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            StartupInfo startup = new StartupInfo();
            startup.Size = (uint)Marshal.SizeOf(typeof(StartupInfo));
            startup.Flags = 0x100;
            startup.Input = input;
            startup.Output = output;
            startup.Error = error;
            var command = new System.Text.StringBuilder("\"" + executable + "\" -u \"" + script + "\"");
            // Suspend before assigning the job so the venv launcher cannot spawn an untracked child.
            if (!CreateProcess(executable, command, IntPtr.Zero, IntPtr.Zero, true, 0x08000004, IntPtr.Zero, directory, ref startup, out process))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            if (!AssignProcessToJobObject(job, process.Process) || ResumeThread(process.Thread) == uint.MaxValue)
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            return (int)process.ProcessId;
        } catch {
            if (process.Process != IntPtr.Zero) TerminateProcess(process.Process, 1);
            throw;
        } finally {
            if (process.Thread != IntPtr.Zero) CloseHandle(process.Thread);
            if (process.Process != IntPtr.Zero) CloseHandle(process.Process);
            if (output != new IntPtr(-1)) CloseHandle(output);
            if (error != new IntPtr(-1)) CloseHandle(error);
            if (input != new IntPtr(-1)) CloseHandle(input);
        }
    }
    public static void Close() {
        if (job != IntPtr.Zero) {
            CloseHandle(job);
            job = IntPtr.Zero;
        }
    }
}
public class HotkeyEventArgs : EventArgs {
    public int Id { get; private set; }
    public HotkeyEventArgs(int id) { Id = id; }
}

public class HotkeyHub : Form {
    [DllImport("user32.dll", SetLastError = true)]
    static extern bool RegisterHotKey(IntPtr hWnd, int id, uint modifiers, uint key);
    [DllImport("user32.dll")]
    static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    private readonly System.Collections.Generic.List<int> _ids = new System.Collections.Generic.List<int>();
    public event EventHandler Pressed;

    public HotkeyHub() {
        ShowInTaskbar = false;
        Opacity = 0;
    }

    public void Register(int id, uint modifiers, uint key, string name) {
        if (!RegisterHotKey(Handle, id, modifiers, key))
            throw new InvalidOperationException("热键 " + name + " 被占用，或入口已经运行。");
        _ids.Add(id);
    }

    protected override void WndProc(ref Message m) {
        if (m.Msg == 0x0312) {
            int id = m.WParam.ToInt32();
            EventHandler handler = Pressed;
            if (handler != null) handler(this, new HotkeyEventArgs(id));
        }
        base.WndProc(ref m);
    }

    protected override void Dispose(bool disposing) {
        foreach (int id in _ids) UnregisterHotKey(Handle, id);
        base.Dispose(disposing);
    }
}
'@ -ReferencedAssemblies System.Windows.Forms
} catch {
    Write-StartupError '编译/初始化失败' $_
    exit 1
}
$hub = $null
$tray = $null
[ScreenshotProcessJob]::Create()
try {
try { $ready = Invoke-RestMethod "$url/probe/" -TimeoutSec 2 } catch { $ready = $null }
if (-not $ready) {
    $serverId = [ScreenshotProcessJob]::Start($python, (Join-Path $PSScriptRoot 'server.py'), $PSScriptRoot)
    $server = Get-Process -Id $serverId
    $deadline = [System.DateTime]::UtcNow.AddMinutes(3)
    do {
        $server.Refresh()
        if ($server.HasExited) { throw '服务启动失败，请查看 logs/server-error.log。' }
        try { $ready = Invoke-RestMethod "$url/probe/" -TimeoutSec 2 } catch { $ready = $null }
        if (-not $ready) { Start-Sleep -Milliseconds 500 }
    } while (-not $ready -and [DateTime]::UtcNow -lt $deadline)
    if (-not $ready) { throw '服务启动超时，请查看 logs/server-error.log。' }
}
$hub = New-Object HotkeyHub
$hub.Register(1, [System.UInt32]0x4003, [System.UInt32]0x77, 'Ctrl+Alt+F8')
$hub.Register(2, [System.UInt32]0x4003, [System.UInt32]0x78, 'Ctrl+Alt+F9')
$hotkeyHint = '截图编号：Ctrl+Alt+F8 全屏 / Ctrl+Alt+F9 框选'
$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = [System.Drawing.SystemIcons]::Application
$tray.Text = $hotkeyHint
$tray.Visible = $true
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$open = $menu.Items.Add('打开本地预览页')
$open.add_Click({ Start-Process $url })
$full = $menu.Items.Add('全屏截图编号（Ctrl+Alt+F8）')
$full.add_Click({ & $run 'FullScreen' })
$region = $menu.Items.Add('框选截图编号（Ctrl+Alt+F9）')
$region.add_Click({ & $run 'Region' })
$clip = $menu.Items.Add('剪贴板图片编号')
$clip.add_Click({ & $run 'Clipboard' })
$exit = $menu.Items.Add('退出程序（关闭本次启动的识别服务）')
$exit.add_Click({ $hub.Close() })
$tray.ContextMenuStrip = $menu
$run = {
    param($Mode)
    try {
        $tray.Text = '正在识别截图……'
        if ($Mode -eq 'Clipboard') {
            $result = & (Join-Path $PSScriptRoot 'scripts\Annotate.ps1')
        } else {
            $result = & (Join-Path $PSScriptRoot 'scripts\Shot.ps1') -Mode $Mode
            if (-not $result) { return }
        }
        $tray.ShowBalloonTip(4000, '编号图已复制', ($result -join "`n"), [System.Windows.Forms.ToolTipIcon]::Info)
    } catch {
        $tray.ShowBalloonTip(5000, '处理失败', $_.Exception.Message, [System.Windows.Forms.ToolTipIcon]::Error)
    } finally {
        $tray.Text = $hotkeyHint
    }
}
$hub.add_Pressed({
    param($Sender, $Args)
    if ($Args.Id -eq 1) { & $run 'FullScreen' } else { & $run 'Region' }
})
$tray.add_DoubleClick({ Start-Process $url })
Start-Process $url
[System.Windows.Forms.Application]::Run($hub)
} catch {
    Write-StartupError '启动/运行失败' $_
    exit 1
} finally {
    if ($tray) { $tray.Dispose() }
    if ($hub) { $hub.Dispose() }
    [ScreenshotProcessJob]::Close()
}

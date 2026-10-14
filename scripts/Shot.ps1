param(
    [Parameter(Mandatory = $true)][ValidateSet('FullScreen', 'Region')][string]$Mode,
    [string]$CapturePath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'output\capture.png')
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

Add-Type -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public static class ShotCapture {
    [DllImport("user32.dll")] private static extern bool SetProcessDPIAware();

    static ShotCapture() {
        try { SetProcessDPIAware(); } catch { }
    }

    public static Bitmap Grab() {
        Rectangle vb = SystemInformation.VirtualScreen;
        Bitmap bmp = new Bitmap(vb.Width, vb.Height, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp))
            g.CopyFromScreen(vb.Left, vb.Top, 0, 0, vb.Size, CopyPixelOperation.SourceCopy);
        return bmp;
    }

    public static string CaptureFullScreen(string path) {
        using (Bitmap bmp = Grab())
            bmp.Save(path, ImageFormat.Png);
        return path;
    }

    public static string CaptureRegion(string path) {
        using (RegionForm form = new RegionForm()) {
            form.ShowDialog();
            if (form.Selected == null) return null;
            form.Selected.Save(path, ImageFormat.Png);
        }
        return path;
    }
}

public class RegionForm : Form {
    private readonly Bitmap _shot;
    private readonly Point _origin;
    private Point _start;
    private Rectangle _sel;
    private bool _drag;

    public RegionForm() {
        Rectangle vb = SystemInformation.VirtualScreen;
        _origin = vb.Location;
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;
        Bounds = vb;
        TopMost = true;
        ShowInTaskbar = false;
        Cursor = Cursors.Cross;
        DoubleBuffered = true;
        _shot = ShotCapture.Grab();
        BackgroundImage = _shot;
    }

    public Bitmap Selected { get; private set; }

    protected override void OnMouseDown(MouseEventArgs e) {
        if (e.Button == MouseButtons.Right) { CancelMe(); return; }
        _drag = true;
        _start = Control.MousePosition;
        _sel = new Rectangle(_start, Size.Empty);
    }

    protected override void OnMouseMove(MouseEventArgs e) {
        if (!_drag) return;
        Point p = Control.MousePosition;
        _sel = new Rectangle(Math.Min(_start.X, p.X), Math.Min(_start.Y, p.Y),
                             Math.Abs(p.X - _start.X), Math.Abs(p.Y - _start.Y));
        Invalidate();
    }

    protected override void OnMouseUp(MouseEventArgs e) {
        if (!_drag) return;
        _drag = false;
        Point p = Control.MousePosition;
        Rectangle r = new Rectangle(Math.Min(_start.X, p.X), Math.Min(_start.Y, p.Y),
                                    Math.Abs(p.X - _start.X), Math.Abs(p.Y - _start.Y));
        if (r.Width > 2 && r.Height > 2) {
            Rectangle local = new Rectangle(r.X - _origin.X, r.Y - _origin.Y, r.Width, r.Height);
            local.Intersect(new Rectangle(Point.Empty, _shot.Size));
            Selected = (Bitmap)_shot.Clone(local, PixelFormat.Format32bppArgb);
            DialogResult = DialogResult.OK;
        } else {
            DialogResult = DialogResult.Cancel;
        }
        Close();
    }

    protected override bool ProcessCmdKey(ref Message m, Keys keyData) {
        if (keyData == Keys.Escape) { CancelMe(); return true; }
        return base.ProcessCmdKey(ref m, keyData);
    }

    private void CancelMe() {
        DialogResult = DialogResult.Cancel;
        Close();
    }

    protected override void OnPaint(PaintEventArgs e) {
        if (!_drag) return;
        Graphics g = e.Graphics;
        Rectangle sel = new Rectangle(_sel.X - _origin.X, _sel.Y - _origin.Y, _sel.Width, _sel.Height);
        using (SolidBrush dim = new SolidBrush(Color.FromArgb(110, 0, 0, 0))) {
            g.FillRectangle(dim, 0, 0, Width, Math.Max(0, sel.Top));
            g.FillRectangle(dim, 0, sel.Bottom, Width, Math.Max(0, Height - sel.Bottom));
            g.FillRectangle(dim, 0, sel.Top, Math.Max(0, sel.Left), sel.Height);
            g.FillRectangle(dim, sel.Right, sel.Top, Math.Max(0, Width - sel.Right), sel.Height);
        }
        Rectangle border = new Rectangle(sel.X, sel.Y, Math.Max(1, sel.Width - 1), Math.Max(1, sel.Height - 1));
        using (Pen dark = new Pen(Color.FromArgb(180, 0, 0, 0), 1))
            g.DrawRectangle(dark, border);
        using (Pen white = new Pen(Color.White, 2)) {
            white.DashStyle = System.Drawing.Drawing2D.DashStyle.Dash;
            g.DrawRectangle(white, border);
        }
        string size = string.Format("{0} x {1}", sel.Width, sel.Height);
        SizeF ts = g.MeasureString(size, Font);
        float tx = (sel.Right + 6 + ts.Width > Width) ? sel.Right - 6 - ts.Width : sel.Right + 6;
        float ty = (sel.Bottom + 6 + ts.Height > Height) ? sel.Bottom - 6 - ts.Height : sel.Bottom + 6;
        using (SolidBrush bg = new SolidBrush(Color.FromArgb(180, 0, 0, 0)))
            g.FillRectangle(bg, tx - 3, ty - 2, ts.Width + 6, ts.Height + 4);
        using (SolidBrush fg = new SolidBrush(Color.White))
            g.DrawString(size, Font, fg, tx, ty);
    }

    protected override void Dispose(bool disposing) {
        if (disposing) {
            BackgroundImage = null;
            if (_shot != null) _shot.Dispose();
            if (Selected != null) Selected.Dispose();
        }
        base.Dispose(disposing);
    }
}
'@ -ReferencedAssemblies System.Drawing, System.Windows.Forms

$captured = if ($Mode -eq 'FullScreen') { [ShotCapture]::CaptureFullScreen($CapturePath) } else { [ShotCapture]::CaptureRegion($CapturePath) }
if (-not $captured) { return }

& (Join-Path $PSScriptRoot 'Annotate.ps1') -InputPath $captured -CopyToClipboard

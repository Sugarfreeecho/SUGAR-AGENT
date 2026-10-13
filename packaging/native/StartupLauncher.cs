using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Pipes;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

// A small GUI entry point appears before unpacking/initializing Electron.
// Windows owns the startup cursor; this application never changes cursor schemes.
internal static class StartupLauncher
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct StartupInfo {
        public int cb; public IntPtr reserved, desktop, title;
        public uint x, y, width, height, xCount, yCount, fill, flags;
        public short show, reservedBytes; public IntPtr reservedPtr, input, output, error;
    }
    [StructLayout(LayoutKind.Sequential)]
    internal struct ProcessInfo { public IntPtr process, thread; public uint pid, tid; }
    [StructLayout(LayoutKind.Sequential)]
    internal struct CursorInfo { public int cb, flags; public IntPtr cursor; public Point position; }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    internal static extern bool CreateProcess(string application, StringBuilder command, IntPtr pa, IntPtr ta,
        bool inherit, uint flags, IntPtr environment, string cwd, ref StartupInfo startup, out ProcessInfo process);
    [DllImport("kernel32.dll")] internal static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")] internal static extern uint WaitForSingleObject(IntPtr handle, uint timeout);
    [DllImport("kernel32.dll")] internal static extern bool GetExitCodeProcess(IntPtr handle, out uint code);
    [DllImport("user32.dll")] internal static extern bool GetCursorInfo(ref CursorInfo info);
    [DllImport("user32.dll")] internal static extern IntPtr LoadCursor(IntPtr instance, IntPtr name);

    // Quote an argv item according to CommandLineToArgvW/CRT rules, including trailing backslashes.
    internal static string Quote(string value) {
        var output = new StringBuilder("\""); int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            output.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
            output.Append(c); slashes = 0;
        }
        output.Append('\\', slashes * 2); return output.Append('"').ToString();
    }
    internal static Stream Resource(string name) {
        return Assembly.GetExecutingAssembly().GetManifestResourceStream(name);
    }
    [STAThread]
    private static int Main(string[] args) {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        using (var splash = new StartupSplash(args)) Application.Run(splash);
        return Environment.ExitCode;
    }

    private sealed class StartupSplash : Form
    {
        private readonly string[] args;
        private readonly bool smoke;
        private readonly string reportPath;
        private readonly string pipeName = "SugarAgent-startup-" + Guid.NewGuid().ToString("N");
        private readonly Dictionary<string, object> report = new Dictionary<string, object>();
        private NamedPipeServerStream pipe;
        private bool handoff;
        private bool childFinished;
        private string temporaryFolder;

        protected override bool ShowWithoutActivation { get { return true; } }
        public StartupSplash(string[] arguments) {
            args = arguments;
            foreach (string arg in args) {
                if (arg == "--launcher-smoke") smoke = true;
                if (arg.StartsWith("--launcher-report=")) reportPath = arg.Substring("--launcher-report=".Length);
            }
            Text = "SugarAgent 正在启动"; ClientSize = new Size(360, 250);
            FormBorderStyle = FormBorderStyle.None; StartPosition = FormStartPosition.CenterScreen;
            ShowInTaskbar = false; BackColor = Color.White; Cursor = Cursors.AppStarting;
            if (smoke) Opacity = 0;
            using (Stream image = Resource("BrandLogo")) {
                using (Image original = Image.FromStream(image)) {
                    Controls.Add(new PictureBox { Image = new Bitmap(original), SizeMode = PictureBoxSizeMode.Zoom,
                        Location = new Point(132, 28), Size = new Size(96, 96) });
                }
            }
            Controls.Add(new Label { Text = "正在启动…", TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Microsoft YaHei UI", 11), ForeColor = Color.FromArgb(37, 37, 43),
                Location = new Point(30, 144), Size = new Size(300, 28) });
            Controls.Add(new ProgressBar { Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 25,
                Location = new Point(70, 194), Size = new Size(220, 8) });
        }
        protected override void OnShown(EventArgs e) {
            base.OnShown(e);
            report["nativeSplashShown"] = true;
            report["splashBeforeChild"] = true;
            report["nativeBusyCursor"] = Cursor == Cursors.AppStarting;
            if (reportPath != null) {
                using (var bitmap = new Bitmap(Width, Height)) {
                    DrawToBitmap(bitmap, new Rectangle(Point.Empty, Size));
                    bitmap.Save(Path.ChangeExtension(reportPath, ".png"));
                }
            }
            var security = new PipeSecurity();
            security.AddAccessRule(new PipeAccessRule(WindowsIdentity.GetCurrent().User,
                PipeAccessRights.FullControl, AccessControlType.Allow));
            pipe = new NamedPipeServerStream(pipeName, PipeDirection.In, 1, PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous, 0, 0, security);
            pipe.BeginWaitForConnection(Ready, null);
            ThreadPool.QueueUserWorkItem(delegate { RunChild(); });
        }
        private void Ready(IAsyncResult result) {
            try {
                pipe.EndWaitForConnection(result);
                byte[] buffer = new byte[5]; int read = 0;
                while (read < buffer.Length) {
                    int count = pipe.Read(buffer, read, buffer.Length - read);
                    if (count == 0) break;
                    read += count;
                }
                if (Encoding.ASCII.GetString(buffer, 0, read) == "ready") {
                    BeginInvoke((MethodInvoker)delegate { handoff = true; Hide(); });
                }
            } catch (ObjectDisposedException) { }
            catch (IOException) { }
            catch (InvalidOperationException) { }
        }
        private void RunChild() {
            ProcessInfo child = new ProcessInfo();
            uint code = 1;
            string failure = null;
            try {
                string target;
                using (var reader = new StreamReader(Resource("LauncherTarget"), Encoding.UTF8)) target = reader.ReadToEnd().Trim();
                using (Stream payload = Resource("PortablePayload")) {
                    if (payload != null) {
                        temporaryFolder = Path.Combine(Path.GetTempPath(), "SugarAgent-startup-demo-" + Guid.NewGuid().ToString("N"));
                        Directory.CreateDirectory(temporaryFolder);
                        target = Path.Combine(temporaryFolder, "StartupDemoPayload.exe");
                        using (var output = File.Create(target)) payload.CopyTo(output);
                    } else {
                        target = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, target);
                    }
                }
                var command = new StringBuilder(Quote(target));
                foreach (string arg in args) {
                    if (arg == "--launcher-smoke" || arg.StartsWith("--launcher-report=")) continue;
                    command.Append(' ').Append(Quote(arg));
                }
                command.Append(' ').Append(Quote("--sugaragent-startup-pipe=" + pipeName));
                var startup = new StartupInfo { cb = Marshal.SizeOf(typeof(StartupInfo)), flags = 0x40 }; // STARTF_FORCEONFEEDBACK
                if (!CreateProcess(target, command, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero,
                    Path.GetDirectoryName(target), ref startup, out child)) throw new Win32Exception(Marshal.GetLastWin32Error());
                CloseHandle(child.thread); child.thread = IntPtr.Zero;
                report["startupFlags"] = startup.flags;
                bool busy = false;
                IntPtr appStarting = LoadCursor(IntPtr.Zero, new IntPtr(32650)); // IDC_APPSTARTING
                while (WaitForSingleObject(child.process, 25) == 258) {
                    if (smoke && !busy) {
                        var cursor = new CursorInfo { cb = Marshal.SizeOf(typeof(CursorInfo)) };
                        busy = GetCursorInfo(ref cursor) && cursor.cursor == appStarting;
                    }
                }
                report["systemBusyCursorObserved"] = busy;
                GetExitCodeProcess(child.process, out code);
            } catch (Exception error) {
                report["error"] = error.ToString();
                failure = error.Message;
            } finally {
                if (child.process != IntPtr.Zero) CloseHandle(child.process);
                if (child.thread != IntPtr.Zero) CloseHandle(child.thread);
                if (temporaryFolder != null) {
                    string resolved = Path.GetFullPath(temporaryFolder);
                    string tempRoot = Path.GetFullPath(Path.GetTempPath()).TrimEnd(Path.DirectorySeparatorChar);
                    if (String.Equals(Path.GetDirectoryName(resolved), tempRoot, StringComparison.OrdinalIgnoreCase)
                        && Path.GetFileName(resolved).StartsWith("SugarAgent-startup-demo-", StringComparison.Ordinal)) {
                        try { Directory.Delete(resolved, true); } catch (IOException) { } catch (UnauthorizedAccessException) { }
                    }
                }
                BeginInvoke((MethodInvoker)delegate {
                    report["handoff"] = handoff; report["childExitCode"] = code;
                    if (reportPath != null) File.WriteAllText(reportPath, new JavaScriptSerializer().Serialize(report), Encoding.UTF8);
                    if (failure != null && !smoke) MessageBox.Show(this, failure, "SugarAgent 无法启动", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    childFinished = true; Environment.ExitCode = (int)code; Close();
                });
            }
        }
        protected override void OnFormClosing(FormClosingEventArgs e) {
            if (!childFinished && e.CloseReason == CloseReason.UserClosing) e.Cancel = true;
            base.OnFormClosing(e);
        }
        protected override void Dispose(bool disposing) {
            if (disposing && pipe != null) pipe.Dispose();
            foreach (Control control in Controls) {
                var picture = control as PictureBox;
                if (picture != null && picture.Image != null) picture.Image.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}

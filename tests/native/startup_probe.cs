using System;
using System.Drawing;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

class StartupProbe {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct StartupInfo {
        public int cb; public IntPtr reserved, desktop, title;
        public uint x, y, width, height, xCount, yCount, fill, flags;
        public short show, reservedBytes; public IntPtr reservedPtr, input, output, error;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern void GetStartupInfo(out StartupInfo info);
    [STAThread] static void Main(string[] args) {
        StartupInfo startup; GetStartupInfo(out startup);
        string report = null, pipeName = null;
        foreach (string arg in args) {
            if (arg.StartsWith("--probe-report=")) report = arg.Substring("--probe-report=".Length);
            if (arg.StartsWith("--sugaragent-startup-pipe=")) pipeName = arg.Substring("--sugaragent-startup-pipe=".Length);
        }
        // Keep the child before its first message loop long enough to observe the OS cursor.
        Thread.Sleep(1000);
        File.WriteAllText(report, new JavaScriptSerializer().Serialize(new { startupFlags = startup.flags, args = args }), Encoding.UTF8);
        if (pipeName != null) {
            using (var pipe = new NamedPipeClientStream(".", pipeName, PipeDirection.Out)) {
                pipe.Connect(3000); byte[] ready = Encoding.ASCII.GetBytes("ready"); pipe.Write(ready, 0, ready.Length);
            }
        }
        Application.EnableVisualStyles();
        using (var form = new Form { Size = new Size(30, 30), Opacity = 0, ShowInTaskbar = false }) {
            var timer = new System.Windows.Forms.Timer { Interval = 200 };
            timer.Tick += delegate { timer.Stop(); form.Close(); };
            form.Shown += delegate { timer.Start(); };
            Application.Run(form);
        }
    }
}

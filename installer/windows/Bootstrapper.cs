using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class Program
{
    internal static string InstallRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "pdomain-ocr-simple-gui");
    [STAThread]
    private static void Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            if (args.Length == 1 && args[0] == "--launch") { Launch(); return; }
            Application.Run(new SetupForm(args.Length == 1 && args[0] == "--uninstall"));
        }
        catch (Exception error) { MessageBox.Show(error.Message, "OCR Simple GUI", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
    internal static ProcessStartInfo PowerShell(string script, string arguments)
    {
        return new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"WindowsPowerShell\v1.0\powershell.exe"), "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"" + script + "\" " + arguments) {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
        };
    }
    internal static void Launch()
    {
        string json = File.ReadAllText(Path.Combine(InstallRoot, "launch.json"));
        var launch = new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string, string>>(json);
        string executable = launch["desktop_executable"];
        if (!File.Exists(executable)) throw new IOException("The installed desktop launcher is missing. Run Setup again to repair the installation.");
        Process.Start(new ProcessStartInfo(executable) { UseShellExecute = false, CreateNoWindow = true });
    }
}

internal sealed class SetupForm : Form
{
    private readonly TextBox log = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Fill };
    private readonly Label status = new Label { Dock = DockStyle.Top, Height = 64, Padding = new Padding(10) };
    private readonly ProgressBar progress = new ProgressBar { Dock = DockStyle.Top, Height = 18 };
    private readonly Button action = new Button { Text = "Install", Width = 110 };
    private readonly Button close = new Button { Text = "Cancel", Width = 110 };
    private readonly bool uninstall;
    private string scratch;
    private bool running;
    private bool complete;

    internal SetupForm(bool removing)
    {
        uninstall = removing;
        Text = uninstall ? "Remove OCR Simple GUI" : "Install OCR Simple GUI";
        Size = new Size(760, 500); MinimumSize = new Size(600, 380); StartPosition = FormStartPosition.CenterScreen;
        status.Text = uninstall ? "Remove OCR Simple GUI? Projects, scans, outputs, model caches and shared tools will be kept." : "Install OCR Simple GUI for this Windows account. Internet is required for Python and OCR dependencies. Windows may request permission for the Microsoft runtime.";
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 45, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(5) };
        buttons.Controls.Add(close); buttons.Controls.Add(action);
        Controls.Add(log); Controls.Add(progress); Controls.Add(status); Controls.Add(buttons);
        action.Text = uninstall ? "Remove" : "Install";
        action.Click += delegate { if (complete) { Program.Launch(); Close(); } else BeginOperation(); };
        close.Click += delegate { Close(); };
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if (running) { e.Cancel = true; MessageBox.Show(this, "Please wait for the current operation to finish. Closing this window cannot safely cancel package installation.", Text); } };
        FormClosed += delegate { if (scratch != null) { try { Directory.Delete(scratch, true); } catch (IOException) { } catch (UnauthorizedAccessException) { } } };
    }
    private void Append(string line)
    {
        if (line == null || IsDisposed) return;
        BeginInvoke((Action)delegate { log.AppendText(line + Environment.NewLine); });
    }
    private void BeginOperation()
    {
        running = true; action.Enabled = false; close.Enabled = false; progress.Style = ProgressBarStyle.Marquee;
        status.Text = uninstall ? "Removing application. Your work will be kept." : "Installing. First installation can take several minutes. Permission requests appear separately.";
        try
        {
            string script;
            if (uninstall) script = Path.Combine(Program.InstallRoot, "uninstall.ps1");
            else
            {
                if (scratch != null) Directory.Delete(scratch, true);
                scratch = Path.Combine(Path.GetTempPath(), "pdomain-setup-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(scratch);
                File.WriteAllText(Path.Combine(scratch, ".nobackup"), "");
                string payloadDirectory = Path.Combine(scratch, "payload");
                Directory.CreateDirectory(payloadDirectory);
                using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
                using (var archive = new ZipArchive(payload, ZipArchiveMode.Read)) { archive.ExtractToDirectory(payloadDirectory); }
                script = Path.Combine(payloadDirectory, "install-desktop.ps1");
            }
            string arguments = uninstall ? "-Yes -ManifestPath \"" + Path.Combine(Program.InstallRoot, "install-manifest.json") + "\"" : "-BootstrapperPath \"" + Application.ExecutablePath + "\"";
            var child = new Process { StartInfo = Program.PowerShell(script, arguments), EnableRaisingEvents = true };
            child.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { Append(e.Data); };
            child.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { Append(e.Data); };
            child.Exited += delegate { child.WaitForExit(); int code = child.ExitCode; child.Dispose(); BeginInvoke((Action)delegate { Finish(code); }); };
            child.Start(); child.BeginOutputReadLine(); child.BeginErrorReadLine();
        }
        catch (Exception error) { Append(error.Message); Finish(1); }
    }
    private void Finish(int code)
    {
        running = false; close.Enabled = true; action.Enabled = true; progress.Style = ProgressBarStyle.Blocks;
        if (code != 0 && code != 3010) { status.Text = "The operation failed. See the details below, then Retry. Your work is kept."; action.Text = "Retry"; return; }
        complete = true; progress.Value = 100; close.Text = "Close";
        status.Text = uninstall ? "OCR Simple GUI was removed. Projects, scans, outputs, shared tools and model caches were kept." : "OCR Simple GUI is installed. Use its Start menu icon to launch the app. Browser-installed icons require starting this native app first.";
        action.Text = "Open app"; action.Visible = !uninstall;
        if (code == 3010) { status.Text = "OCR Simple GUI is installed. The Microsoft runtime requires a Windows restart before OCR can run. Restart when convenient, then use the Start menu icon."; action.Visible = false; }
        if (uninstall)
        {
            string exe = Application.ExecutablePath;
            if (String.Equals(Path.GetFullPath(exe), Path.Combine(Program.InstallRoot, "OCR-Simple-GUI.exe"), StringComparison.OrdinalIgnoreCase))
            {
                string escaped = exe.Replace("'", "''");
                string cleanup = "Wait-Process -Id " + Process.GetCurrentProcess().Id + " -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '" + escaped + "' -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '" + Program.InstallRoot.Replace("'", "''") + "' -ErrorAction SilentlyContinue";
                Process.Start(new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"WindowsPowerShell\v1.0\powershell.exe"), "-NoProfile -NonInteractive -EncodedCommand " + Convert.ToBase64String(Encoding.Unicode.GetBytes(cleanup))) { UseShellExecute = false, CreateNoWindow = true });
            }
        }
    }
}

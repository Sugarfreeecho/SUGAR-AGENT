using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

internal static class SugarAgentEgressHelper
{
    const int Protocol = 1;
    const uint EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
    const uint INFINITE = 0xffffffff;
    const int ERROR_ALREADY_EXISTS = 183;
    const int PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009;
    const string ProfileName = "SugarAgent.Egress.NoNetwork";

    [StructLayout(LayoutKind.Sequential)] struct SECURITY_CAPABILITIES { public IntPtr AppContainerSid; public IntPtr Capabilities; public uint CapabilityCount; public uint Reserved; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] struct STARTUPINFO { public int cb; public string lpReserved; public string lpDesktop; public string lpTitle; public uint dwX; public uint dwY; public uint dwXSize; public uint dwYSize; public uint dwXCountChars; public uint dwYCountChars; public uint dwFillAttribute; public uint dwFlags; public short wShowWindow; public short cbReserved2; public IntPtr lpReserved2; public IntPtr hStdInput; public IntPtr hStdOutput; public IntPtr hStdError; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] struct STARTUPINFOEX { public STARTUPINFO StartupInfo; public IntPtr lpAttributeList; }
    [StructLayout(LayoutKind.Sequential)] struct PROCESS_INFORMATION { public IntPtr hProcess; public IntPtr hThread; public uint dwProcessId; public uint dwThreadId; }

    [DllImport("userenv.dll", CharSet = CharSet.Unicode)] static extern int CreateAppContainerProfile(string name, string displayName, string description, IntPtr capabilities, uint count, out IntPtr sid);
    [DllImport("userenv.dll", CharSet = CharSet.Unicode)] static extern int DeriveAppContainerSidFromAppContainerName(string name, out IntPtr sid);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool InitializeProcThreadAttributeList(IntPtr list, int count, int flags, ref IntPtr size);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool UpdateProcThreadAttribute(IntPtr list, uint flags, IntPtr attribute, IntPtr value, IntPtr size, IntPtr previous, IntPtr returned);
    [DllImport("kernel32.dll")] static extern void DeleteProcThreadAttributeList(IntPtr list);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool CreateProcessW(string application, StringBuilder commandLine, IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles, uint flags, IntPtr environment, string currentDirectory, ref STARTUPINFOEX startup, out PROCESS_INFORMATION info);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, EntryPoint = "ConvertSidToStringSidW", SetLastError = true)] static extern bool ConvertSidToStringSid(IntPtr sid, out IntPtr text);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetHandleInformation(IntPtr handle, uint mask, uint flags);

    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    static string Canonical(IDictionary<string, object> value)
    {
        var keys = new List<string>(value.Keys); keys.Sort(StringComparer.Ordinal);
        var parts = new List<string>();
        foreach (var key in keys) parts.Add(Json.Serialize(key) + ":" + CanonicalValue(value[key]));
        return "{" + string.Join(",", parts.ToArray()) + "}";
    }

    static string CanonicalValue(object value)
    {
        var dict = value as IDictionary<string, object>;
        if (dict != null) return Canonical(dict);
        var array = value as System.Collections.IEnumerable;
        if (array != null && !(value is string)) { var items = new List<string>(); foreach (var item in array) items.Add(CanonicalValue(item)); return "[" + string.Join(",", items.ToArray()) + "]"; }
        return Json.Serialize(value);
    }

    static byte[] Base64Url(string raw)
    {
        raw = raw.Replace('-', '+').Replace('_', '/');
        raw += new string('=', (4 - raw.Length % 4) % 4);
        return Convert.FromBase64String(raw);
    }

    static bool FixedEquals(string a, string b)
    {
        if (a == null || b == null || a.Length != b.Length) return false;
        int diff = 0; for (int i = 0; i < a.Length; i++) diff |= a[i] ^ b[i]; return diff == 0;
    }

    static IDictionary<string, object> VerifyTicket(string encoded)
    {
        var envelope = Json.Deserialize<Dictionary<string, object>>(Encoding.UTF8.GetString(Base64Url(encoded)));
        var payload = (IDictionary<string, object>)envelope["payload"];
        byte[] key = Base64Url(Environment.GetEnvironmentVariable("SUGAR_AGENT_EGRESS_SESSION_KEY") ?? "");
        string expected;
        using (var hmac = new HMACSHA256(key)) expected = BitConverter.ToString(hmac.ComputeHash(Encoding.UTF8.GetBytes(Canonical(payload)))).Replace("-", "").ToLowerInvariant();
        if (!FixedEquals(expected, Convert.ToString(envelope["signature"]))) throw new InvalidDataException("ticket signature mismatch");
        if (Convert.ToInt32(payload["version"]) != Protocol) throw new InvalidDataException("unsupported ticket protocol");
        long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        if (now < Convert.ToInt64(payload["issued_at"]) - 30 || now > Convert.ToInt64(payload["expires_at"])) throw new InvalidDataException("ticket expired or not active");
        if (!FixedEquals(Convert.ToString(payload["command_digest"]), Environment.GetEnvironmentVariable("SUGAR_AGENT_EGRESS_COMMAND_DIGEST"))) throw new InvalidDataException("command digest mismatch");
        ClaimNonce(Convert.ToString(payload["session_id"]), Convert.ToString(payload["nonce"]));
        return payload;
    }

    static void ClaimNonce(string session, string nonce)
    {
        string root = Path.Combine(Path.GetTempPath(), "sugaragent-egress-nonces", Sha256(session).Substring(0, 24)); Directory.CreateDirectory(root);
        string marker = Path.Combine(root, Sha256(nonce) + ".used");
        try { using (new FileStream(marker, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { } }
        catch (IOException) { throw new InvalidDataException("ticket nonce was already used"); }
    }

    static string Sha256(string value) { using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(value ?? ""))).Replace("-", "").ToLowerInvariant(); }

    static IntPtr ProfileSid()
    {
        IntPtr sid; int hr = CreateAppContainerProfile(ProfileName, "SugarAgent no-network commands", "Commands without an approved egress ticket", IntPtr.Zero, 0, out sid);
        if (hr != 0 && (hr & 0xffff) != ERROR_ALREADY_EXISTS) Marshal.ThrowExceptionForHR(hr);
        if (hr != 0) { hr = DeriveAppContainerSidFromAppContainerName(ProfileName, out sid); if (hr != 0) Marshal.ThrowExceptionForHR(hr); }
        return sid;
    }

    static string ProfileSidText()
    {
        IntPtr sid = ProfileSid(), text;
        try { if (!ConvertSidToStringSid(sid, out text)) throw new System.ComponentModel.Win32Exception(); try { return Marshal.PtrToStringUni(text); } finally { LocalFree(text); } }
        finally { LocalFree(sid); }
    }

    static string Quote(string arg)
    {
        if (arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '\n', '\v', '"' }) < 0) return arg;
        var b = new StringBuilder("\""); int slashes = 0;
        foreach (char c in arg) { if (c == '\\') { slashes++; continue; } if (c == '"') { b.Append('\\', slashes * 2 + 1).Append(c); slashes = 0; } else { b.Append('\\', slashes).Append(c); slashes = 0; } }
        b.Append('\\', slashes * 2).Append('"'); return b.ToString();
    }

    static int LaunchNormal(string[] command)
    {
        var info = new ProcessStartInfo { FileName = command[0], UseShellExecute = false };
        for (int i = 1; i < command.Length; i++) info.Arguments += (i == 1 ? "" : " ") + Quote(command[i]);
        using (var process = Process.Start(info)) { process.WaitForExit(); return process.ExitCode; }
    }

    static int LaunchNoNetwork(string[] command, IDictionary<string, object> payload)
    {
        command[0] = ResolveExecutable(command[0]);
        IntPtr sid = ProfileSid(), list = IntPtr.Zero, capabilitiesPtr = IntPtr.Zero;
        var info = new PROCESS_INFORMATION();
        try {
            IntPtr size = IntPtr.Zero; InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref size);
            list = Marshal.AllocHGlobal(size); if (!InitializeProcThreadAttributeList(list, 1, 0, ref size)) throw new System.ComponentModel.Win32Exception();
            var capabilities = new SECURITY_CAPABILITIES { AppContainerSid = sid, Capabilities = IntPtr.Zero, CapabilityCount = 0, Reserved = 0 };
            capabilitiesPtr = Marshal.AllocHGlobal(Marshal.SizeOf(capabilities)); Marshal.StructureToPtr(capabilities, capabilitiesPtr, false);
            if (!UpdateProcThreadAttribute(list, 0, (IntPtr)PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES, capabilitiesPtr, (IntPtr)Marshal.SizeOf(capabilities), IntPtr.Zero, IntPtr.Zero)) throw new System.ComponentModel.Win32Exception();
            var startup = new STARTUPINFOEX(); startup.StartupInfo.cb = Marshal.SizeOf(startup); startup.lpAttributeList = list;
            startup.StartupInfo.hStdInput = GetStdHandle(-10);
            startup.StartupInfo.hStdOutput = GetStdHandle(-11);
            startup.StartupInfo.hStdError = GetStdHandle(-12);
            startup.StartupInfo.dwFlags = 0x00000100;
            SetHandleInformation(startup.StartupInfo.hStdInput, 1, 1); SetHandleInformation(startup.StartupInfo.hStdOutput, 1, 1); SetHandleInformation(startup.StartupInfo.hStdError, 1, 1);
            var line = new StringBuilder(); foreach (string item in command) { if (line.Length > 0) line.Append(' '); line.Append(Quote(item)); }
            string childDirectory = Environment.CurrentDirectory;
            if (!CreateProcessW(null, line, IntPtr.Zero, IntPtr.Zero, true, EXTENDED_STARTUPINFO_PRESENT, IntPtr.Zero, childDirectory, ref startup, out info)) {
                int code = Marshal.GetLastWin32Error();
                throw new System.ComponentModel.Win32Exception(code, "CreateProcessW failed (" + code + ") for " + command[0] + " in " + Environment.CurrentDirectory);
            }
            WaitForSingleObject(info.hProcess, INFINITE); uint exit; if (!GetExitCodeProcess(info.hProcess, out exit)) throw new System.ComponentModel.Win32Exception(); return unchecked((int)exit);
        } finally { if (info.hThread != IntPtr.Zero) CloseHandle(info.hThread); if (info.hProcess != IntPtr.Zero) CloseHandle(info.hProcess); if (list != IntPtr.Zero) { DeleteProcThreadAttributeList(list); Marshal.FreeHGlobal(list); } if (capabilitiesPtr != IntPtr.Zero) Marshal.FreeHGlobal(capabilitiesPtr); if (sid != IntPtr.Zero) LocalFree(sid); }
    }

    static string ResolveExecutable(string executable)
    {
        if (Path.IsPathRooted(executable) && File.Exists(executable)) return executable;
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        string[] extensions = Path.HasExtension(executable) ? new[] { "" } : (Environment.GetEnvironmentVariable("PATHEXT") ?? ".COM;.EXE;.BAT;.CMD").Split(';');
        foreach (string directory in path.Split(Path.PathSeparator)) foreach (string extension in extensions) {
            string candidate = Path.Combine(directory.Trim('"'), executable + extension);
            if (File.Exists(candidate)) return candidate;
        }
        return executable;
    }

    [DllImport("kernel32.dll")] static extern IntPtr GetStdHandle(int which);

    static int Main(string[] args)
    {
        try {
            Console.OutputEncoding = Encoding.UTF8;
            if (args.Length == 2 && args[0] == "health" && args[1] == "--json") {
                string sid = ProfileSidText();
                Console.WriteLine(Json.Serialize(new { protocol = Protocol, enforcement = "partial", backend = "windows-appcontainer", capabilities = new[] { "deny-network", "process-tree", "ipv4", "ipv6", "dns" }, reason = "Approved network commands are not destination-limited", appcontainer_sid = sid })); return 0;
            }
            if (args.Length >= 5 && args[0] == "launch" && args[1] == "--ticket") {
                int marker = Array.IndexOf(args, "--", 3); if (marker < 0 || marker == args.Length - 1) throw new InvalidDataException("missing command");
                var payload = VerifyTicket(args[2]); Environment.SetEnvironmentVariable("SUGAR_AGENT_EGRESS_SESSION_KEY", null); Environment.SetEnvironmentVariable("SUGAR_AGENT_EGRESS_COMMAND_DIGEST", null);
                var command = new string[args.Length - marker - 1]; Array.Copy(args, marker + 1, command, 0, command.Length);
                return Convert.ToString(payload["network"]) == "deny" ? LaunchNoNetwork(command, payload) : LaunchNormal(command);
            }
            Console.Error.WriteLine("usage: sugaragent-egress-helper health --json | launch --ticket TICKET -- command ..."); return 64;
        } catch (Exception exc) { Console.Error.WriteLine("egress helper: " + exc.Message); return 69; }
    }
}

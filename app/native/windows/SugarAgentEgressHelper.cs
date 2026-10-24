using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Web.Script.Serialization;
using Microsoft.Win32.SafeHandles;

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
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    static extern SafeFileHandle CreateFileW(string name, uint access, uint share, IntPtr attributes, uint creation, uint flags, IntPtr template);

    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    static string Canonical(IDictionary<string, object> value)
    {
        var keys = new List<string>(value.Keys); keys.Sort(StringComparer.Ordinal);
        var parts = new List<string>();
        foreach (var key in keys) parts.Add(CanonicalString(key) + ":" + CanonicalValue(value[key]));
        return "{" + string.Join(",", parts.ToArray()) + "}";
    }

    static string CanonicalValue(object value)
    {
        if (value is string) return CanonicalString((string)value);
        var dict = value as IDictionary<string, object>;
        if (dict != null) return Canonical(dict);
        var array = value as System.Collections.IEnumerable;
        if (array != null && !(value is string)) { var items = new List<string>(); foreach (var item in array) items.Add(CanonicalValue(item)); return "[" + string.Join(",", items.ToArray()) + "]"; }
        return Json.Serialize(value);
    }

    static string CanonicalString(string value)
    {
        // Match Python json.dumps(ensure_ascii=False), including apostrophes
        // and HTML characters which JavaScriptSerializer unnecessarily escapes.
        var result = new StringBuilder("\"");
        foreach (char c in value) {
            switch (c) {
                case '"': result.Append("\\\""); break;
                case '\\': result.Append("\\\\"); break;
                case '\b': result.Append("\\b"); break;
                case '\f': result.Append("\\f"); break;
                case '\n': result.Append("\\n"); break;
                case '\r': result.Append("\\r"); break;
                case '\t': result.Append("\\t"); break;
                default:
                    if (c < 32) result.Append("\\u").Append(((int)c).ToString("x4"));
                    else result.Append(c);
                    break;
            }
        }
        return result.Append('"').ToString();
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
        // Owned per-run TEMP paths can push the marker beyond MAX_PATH. Keep
        // the same exclusive CREATE_NEW claim using the extended Win32 path;
        // an I/O failure must remain closed and must not be called a replay.
        string nativePath = marker.StartsWith(@"\\?\", StringComparison.Ordinal) ? marker :
            marker.StartsWith(@"\\", StringComparison.Ordinal) ? @"\\?\UNC\" + marker.Substring(2) : @"\\?\" + marker;
        using (var handle = CreateFileW(nativePath, 0x40000000, 0, IntPtr.Zero, 1, 0x80, IntPtr.Zero)) {
            if (handle.IsInvalid) {
                int error = Marshal.GetLastWin32Error();
                if (error == 80 || error == ERROR_ALREADY_EXISTS) throw new InvalidDataException("ticket nonce was already used");
                throw new System.ComponentModel.Win32Exception(error, "cannot claim ticket nonce (" + error + ")");
            }
        }
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
            PrepareFilesystem(payload, sid);
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
                throw new System.ComponentModel.Win32Exception(code, "CreateProcessW failed (" + code + ") for " + command[0] + " in " + Environment.CurrentDirectory + "; verify AppContainer access to the executable, its dependencies and working directory");
            }
            WaitForSingleObject(info.hProcess, INFINITE); uint exit; if (!GetExitCodeProcess(info.hProcess, out exit)) throw new System.ComponentModel.Win32Exception(); return unchecked((int)exit);
        } finally { if (info.hThread != IntPtr.Zero) CloseHandle(info.hThread); if (info.hProcess != IntPtr.Zero) CloseHandle(info.hProcess); if (list != IntPtr.Zero) { DeleteProcThreadAttributeList(list); Marshal.FreeHGlobal(list); } if (capabilitiesPtr != IntPtr.Zero) Marshal.FreeHGlobal(capabilitiesPtr); if (sid != IntPtr.Zero) LocalFree(sid); }
    }

    static bool HasDirectoryGrant(DirectorySecurity acl, SecurityIdentifier sid,
                                  FileSystemRights rights, bool inherit)
    {
        uint self = 0, children = 0, required = (uint)rights;
        foreach (FileSystemAccessRule rule in acl.GetAccessRules(true, true, typeof(SecurityIdentifier))) {
            if ((!sid.Equals(rule.IdentityReference) && rule.IdentityReference.Value != "S-1-15-2-1") ||
                rule.AccessControlType != AccessControlType.Allow) continue;
            // Windows directories commonly split self/child ACEs and use
            // generic rights on the inheritable (inherit-only) rule.
            uint mask = unchecked((uint)(int)rule.FileSystemRights), expanded = mask & 0x0fffffff;
            if ((mask & 0x80000000) != 0) expanded |= 0x00120089; // FILE_GENERIC_READ
            if ((mask & 0x40000000) != 0) expanded |= 0x00120116; // FILE_GENERIC_WRITE
            if ((mask & 0x20000000) != 0) expanded |= 0x001200a0; // FILE_GENERIC_EXECUTE
            if ((mask & 0x10000000) != 0) expanded |= 0x001f01ff; // FILE_ALL_ACCESS
            if ((rule.PropagationFlags & PropagationFlags.InheritOnly) == 0) self |= expanded;
            if ((rule.PropagationFlags & PropagationFlags.NoPropagateInherit) == 0 &&
                (rule.InheritanceFlags & (InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit)) ==
                (InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit)) children |= expanded;
        }
        return (self & required) == required && (!inherit || (children & required) == required);
    }

    static void GrantDirectory(string path, SecurityIdentifier sid, FileSystemRights rights, bool inherit)
    {
        try {
            var directory = new DirectoryInfo(Path.GetFullPath(path));
            var acl = directory.GetAccessControl(AccessControlSections.Access);
            if (HasDirectoryGrant(acl, sid, rights, inherit)) return;
            // Preserve unrelated ACEs, ownership and mandatory integrity labels.
            acl.AddAccessRule(new FileSystemAccessRule(sid, rights,
                inherit ? InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit : InheritanceFlags.None,
                PropagationFlags.None, AccessControlType.Allow));
            directory.SetAccessControl(acl);
        } catch (Exception exc) {
            throw new IOException("Cannot prepare AppContainer directory access for '" + path +
                "': " + exc.Message + ". Grant this directory with scripts/build_egress_helper_windows.ps1 -InstallAcl -WorkDir <directory> if its ACL is administrator-managed.", exc);
        }
    }

    static void PrepareFilesystem(IDictionary<string, object> payload, IntPtr sidPointer)
    {
        object raw;
        if (!payload.TryGetValue("filesystem", out raw))
            return; // Legacy runtimes keep their existing ACL-only behavior.
        var filesystem = raw as IDictionary<string, object>;
        if (filesystem == null) throw new InvalidDataException("invalid filesystem grants");
        var sid = new SecurityIdentifier(sidPointer);
        foreach (string key in new[] { "read_dirs", "write_dirs" }) {
            object entries;
            if (!filesystem.TryGetValue(key, out entries) || !(entries is System.Collections.IEnumerable) || entries is string)
                throw new InvalidDataException("invalid filesystem grant list");
            foreach (object entry in (System.Collections.IEnumerable)entries) {
                string path = Convert.ToString(entry);
                if (string.IsNullOrWhiteSpace(path) || !Path.IsPathRooted(path) || !Directory.Exists(path))
                    throw new InvalidDataException("filesystem grant must name an existing absolute directory: " + path);
                GrantDirectory(path, sid, key == "write_dirs" ? FileSystemRights.Modify : FileSystemRights.ReadAndExecute, true);
            }
        }
        // Windows rewrites TEMP/TMP when it creates the AppContainer. The shell
        // restores them from this signed, runtime-owned scratch after startup.
        Environment.SetEnvironmentVariable("SUGAR_AGENT_EGRESS_SCRATCH", null);
        object scratch;
        if (filesystem.TryGetValue("scratch_dirs", out scratch) && scratch is System.Collections.IEnumerable && !(scratch is string))
            foreach (object entry in (System.Collections.IEnumerable)scratch) {
                string path = Convert.ToString(entry); bool authorized = false;
                foreach (object writable in (System.Collections.IEnumerable)filesystem["write_dirs"])
                    if (string.Equals(path, Convert.ToString(writable), StringComparison.OrdinalIgnoreCase)) authorized = true;
                if (!authorized) throw new InvalidDataException("scratch directory is not writable in this ticket");
                Environment.SetEnvironmentVariable("SUGAR_AGENT_EGRESS_SCRATCH", path);
            }
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
                Console.WriteLine(Json.Serialize(new { protocol = Protocol, enforcement = "partial", backend = "windows-appcontainer", capabilities = new[] { "deny-network", "process-tree", "ipv4", "ipv6", "dns", "filesystem-grants" }, reason = "Approved network commands are not destination-limited", appcontainer_sid = sid })); return 0;
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

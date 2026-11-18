using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

// Use the Unicode shell interfaces: WScript.Shell loses some non-ANSI paths.
public static class HciWindowsShortcutV1 {
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int length, IntPtr findData, uint flags);
        void GetIDList(out IntPtr list);
        void SetIDList(IntPtr list);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder value, int length);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string value);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder value, int length);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string value);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder value, int length);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string value);
        void GetHotkey(out short value);
        void SetHotkey(short value);
        void GetShowCmd(out int value);
        void SetShowCmd(int value);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder value, int length, out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string value, int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string value, uint reserved);
        void Resolve(IntPtr window, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string value);
    }
    private static object Create() { return Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("00021401-0000-0000-C000-000000000046"))); }
    public static void Save(string file, string target, string arguments, string working, string icon, string description) {
        object instance = Create();
        try {
            IShellLinkW link = (IShellLinkW)instance;
            link.SetPath(target); link.SetArguments(arguments); link.SetWorkingDirectory(working);
            link.SetIconLocation(icon, 0); link.SetDescription(description); link.SetShowCmd(0);
            ((IPersistFile)instance).Save(file, true);
        } finally { Marshal.FinalReleaseComObject(instance); }
    }
    public static string[] Load(string file) {
        object instance = Create();
        try {
            ((IPersistFile)instance).Load(file, 0);
            IShellLinkW link = (IShellLinkW)instance;
            StringBuilder description = new StringBuilder(32768), arguments = new StringBuilder(32768);
            link.GetDescription(description, description.Capacity); link.GetArguments(arguments, arguments.Capacity);
            return new string[] {description.ToString(), arguments.ToString()};
        } finally { Marshal.FinalReleaseComObject(instance); }
    }
}

using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

// The helper as a native library, for a platform that starts no second process (examples/ios): the same
// request loop, reading requests from one pipe and writing replies to another (pokeldn/pokemon.py _Library).
static class Library
{
    [UnmanagedCallersOnly(EntryPoint = "pokeldn_pkhex_serve")]
    static void Serve(int requests, int replies)
    {
        var input = new FileStream(new SafeFileHandle(requests, ownsHandle: true), FileAccess.Read);
        var output = new FileStream(new SafeFileHandle(replies, ownsHandle: true), FileAccess.Write);
        Console.SetIn(new StreamReader(input));
        Console.SetOut(new StreamWriter(output) { AutoFlush = true });
        Program.Serve();
        Console.Out.Flush();
        output.Dispose();
    }
}

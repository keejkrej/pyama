using Python.Runtime;

namespace PyamaBlazor.Services;

public class PythonService : IPythonService
{
    private bool _disposed;
    private readonly object _lock = new();

    public bool IsInitialized { get; private set; }

    public void Initialize()
    {
        if (IsInitialized) return;

        lock (_lock)
        {
            if (IsInitialized) return;

            var appDir = AppContext.BaseDirectory;
            var pythonHome = Path.Combine(appDir, "python");
            var pythonDll = Path.Combine(pythonHome, "python311.dll");

            // Check if bundled Python exists, otherwise use system Python
            if (File.Exists(pythonDll))
            {
                Environment.SetEnvironmentVariable("PYTHONHOME", pythonHome);
                Environment.SetEnvironmentVariable("PYTHONPATH",
                    Path.Combine(pythonHome, "Lib", "site-packages"));
                Runtime.PythonDLL = pythonDll;
            }
            else
            {
                // Fallback: find system Python
                var systemPython = FindSystemPython();
                if (systemPython != null)
                {
                    Runtime.PythonDLL = systemPython;
                }
            }

            PythonEngine.Initialize();
            IsInitialized = true;
        }
    }

    private static string? FindSystemPython()
    {
        // Try common Python locations on Windows
        var possiblePaths = new[]
        {
            @"C:\Python311\python311.dll",
            @"C:\Python312\python312.dll",
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                @"Programs\Python\Python311\python311.dll"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                @"Programs\Python\Python312\python312.dll"),
        };

        return possiblePaths.FirstOrDefault(File.Exists);
    }

    public async Task<T> RunAsync<T>(Func<T> pythonAction)
    {
        if (!IsInitialized)
            Initialize();

        return await Task.Run(() =>
        {
            using (Py.GIL())
            {
                return pythonAction();
            }
        });
    }

    public async Task RunAsync(Action pythonAction)
    {
        if (!IsInitialized)
            Initialize();

        await Task.Run(() =>
        {
            using (Py.GIL())
            {
                pythonAction();
            }
        });
    }

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    protected virtual void Dispose(bool disposing)
    {
        if (_disposed) return;

        if (disposing && IsInitialized)
        {
            PythonEngine.Shutdown();
        }

        _disposed = true;
    }
}

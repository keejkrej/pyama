using PyamaBlazor.Models;

namespace PyamaBlazor.Services;

public interface IPythonService : IDisposable
{
    bool IsInitialized { get; }
    void Initialize();
    Task<T> RunAsync<T>(Func<T> pythonAction);
    Task RunAsync(Action pythonAction);
}

using PyamaBlazor.Models;

namespace PyamaBlazor.Services;

public interface IAnalysisService
{
    Task<List<string>> GetAvailableModels();
    Task<ModelInfo?> GetModelInfo(string modelName);
    Task<FittingSummary> RunFittingAsync(
        FittingConfig config,
        IProgress<JobProgress>? progress = null,
        CancellationToken ct = default);
}

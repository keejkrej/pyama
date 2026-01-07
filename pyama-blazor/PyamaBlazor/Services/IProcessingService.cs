using PyamaBlazor.Models;

namespace PyamaBlazor.Services;

public interface IProcessingService
{
    Task<MicroscopyMetadata?> LoadMetadataAsync(string filePath);
    Task<List<string>> GetPhaseFeatures();
    Task<List<string>> GetFluorescenceFeatures();
    Task<bool> RunWorkflowAsync(
        WorkflowConfig config,
        IProgress<JobProgress>? progress = null,
        CancellationToken ct = default);
}

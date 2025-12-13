using Python.Runtime;
using PyamaBlazor.Models;

namespace PyamaBlazor.Services;

public class ProcessingService : IProcessingService
{
    private readonly IPythonService _python;

    public ProcessingService(IPythonService python)
    {
        _python = python;
    }

    public async Task<MicroscopyMetadata?> LoadMetadataAsync(string filePath)
    {
        return await _python.RunAsync(() =>
        {
            dynamic io = Py.Import("pyama_core.io");
            dynamic result = io.load_microscopy_file(filePath);
            dynamic metadata = result[1];

            return new MicroscopyMetadata
            {
                FilePath = filePath,
                BaseName = Path.GetFileNameWithoutExtension(filePath),
                NFovs = (int)metadata.n_fovs,
                NFrames = (int)metadata.n_t,
                NChannels = (int)metadata.n_channels,
                ChannelNames = ((IEnumerable<dynamic>)metadata.channel_names)
                    .Select(x => (string)x).ToList(),
                Height = (int)metadata.shape[0],
                Width = (int)metadata.shape[1],
            };
        });
    }

    public async Task<List<string>> GetPhaseFeatures()
    {
        return await _python.RunAsync(() =>
        {
            dynamic features = Py.Import("pyama_core.processing.extraction.features");
            var result = features.list_phase_features();
            return ((IEnumerable<dynamic>)result).Select(x => (string)x).ToList();
        });
    }

    public async Task<List<string>> GetFluorescenceFeatures()
    {
        return await _python.RunAsync(() =>
        {
            dynamic features = Py.Import("pyama_core.processing.extraction.features");
            var result = features.list_fluorescence_features();
            return ((IEnumerable<dynamic>)result).Select(x => (string)x).ToList();
        });
    }

    public async Task<bool> RunWorkflowAsync(
        WorkflowConfig config,
        IProgress<JobProgress>? progress = null,
        CancellationToken ct = default)
    {
        return await _python.RunAsync(() =>
        {
            dynamic io = Py.Import("pyama_core.io");
            dynamic workflow = Py.Import("pyama_core.processing.workflow");
            dynamic types = Py.Import("pyama_core.types.processing");

            // Load metadata
            dynamic loadResult = io.load_microscopy_file(config.MicroscopyPath);
            dynamic metadata = loadResult[1];

            // Build channel selections
            dynamic? pcSelection = config.Config.Channels.PhaseContrast != null
                ? types.ChannelSelection(
                    channel: config.Config.Channels.PhaseContrast.Channel,
                    features: config.Config.Channels.PhaseContrast.Features.ToPython())
                : null;

            var flSelections = new PyList();
            foreach (var fl in config.Config.Channels.Fluorescence)
            {
                var flSel = types.ChannelSelection(
                    channel: fl.Channel,
                    features: fl.Features.ToPython());
                flSelections.Append(flSel);
            }

            dynamic channels = types.Channels(pc: pcSelection, fl: flSelections);

            // Build processing config
            dynamic processingConfig = types.ProcessingConfig(
                output_dir: config.Config.OutputDir,
                channels: channels,
                @params: new PyDict());

            // Run workflow
            var result = workflow.run_complete_workflow(
                metadata: metadata,
                config: processingConfig,
                fov_start: config.FovStart,
                fov_end: config.FovEnd,
                batch_size: config.BatchSize,
                n_workers: config.Workers);

            return (bool)result;
        });
    }
}

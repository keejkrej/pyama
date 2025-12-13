namespace PyamaBlazor.Models;

public class ChannelSelection
{
    public int Channel { get; set; }
    public List<string> Features { get; set; } = [];
}

public class Channels
{
    public ChannelSelection? PhaseContrast { get; set; }
    public List<ChannelSelection> Fluorescence { get; set; } = [];
}

public class ProcessingConfig
{
    public string OutputDir { get; set; } = string.Empty;
    public Channels Channels { get; set; } = new();
    public Dictionary<string, object> Parameters { get; set; } = [];
}

public class WorkflowConfig
{
    public string MicroscopyPath { get; set; } = string.Empty;
    public ProcessingConfig Config { get; set; } = new();
    public int FovStart { get; set; }
    public int FovEnd { get; set; }
    public int BatchSize { get; set; } = 2;
    public int Workers { get; set; } = 2;
}

public class JobProgress
{
    public int CurrentFov { get; set; }
    public int TotalFovs { get; set; }
    public string Message { get; set; } = string.Empty;
    public double Percentage => TotalFovs > 0 ? (double)CurrentFov / TotalFovs * 100 : 0;
}

public class MicroscopyMetadata
{
    public string FilePath { get; set; } = string.Empty;
    public string BaseName { get; set; } = string.Empty;
    public int NFovs { get; set; }
    public int NFrames { get; set; }
    public int NChannels { get; set; }
    public List<string> ChannelNames { get; set; } = [];
    public int Height { get; set; }
    public int Width { get; set; }
}

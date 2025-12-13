# PyAMA-Blazor

PyAMA-Blazor is a .NET MAUI Blazor Hybrid desktop application that provides a modern cross-platform UI for microscopy image analysis. It serves as a next-generation replacement for PyAMA-Pro (Qt/Python), leveraging Python.NET to directly interop with pyama-core for business logic.

## Technology Stack

- **Framework**: .NET 8+ MAUI with Blazor Hybrid
- **UI**: MudBlazor components (Material Design)
- **Python Integration**: Python.NET for pyama-core interop
- **Architecture**: MVVM pattern with C# models
- **Platforms**: Windows, macOS, Linux (future)

## Prerequisites

- .NET 8 SDK with MAUI workload
- Python 3.11+ with pyama-core installed
- Windows 10/11 (primary development platform)

## Installation and Setup

### .NET Prerequisites

```bash
# Install .NET 8 SDK
# Download from https://dotnet.microsoft.com/download

# Install MAUI workload
dotnet workload install maui-windows
# For macOS: dotnet workload install maui-maccatalyst
```

### Python Environment

```bash
# Ensure pyama-core is available
cd path/to/pyama
uv pip install -e pyama-core/
# or pip install -e pyama-core/
```

### Application Setup

```bash
cd PyamaBlazor

# Restore dependencies
dotnet restore

# Build the application
dotnet build

# Run in development
dotnet run
```

## Architecture

```
pyama-blazor/
├── PyamaBlazor/
│   ├── Components/
│   │   ├── Layout/          # MainLayout, NavMenu, SidePanel
│   │   └── Pages/           # Processing, Visualization, Analysis
│   ├── Models/              # C# data models interop with Python
│   ├── Services/            # Python.NET interop services
│   │   ├── PythonService.cs # Python engine management
│   │   └── PyamaCoreService.cs # Workflow methods
│   ├── ViewModels/          # MVVM view models
│   └── wwwroot/             # Static assets, images
└── README.md
```

### Python Integration Architecture

```csharp
// Services/PythonService.cs
public class PythonService : IDisposable
{
    private PyObject _engine;
    private bool _initialized;
    
    public async Task InitializeAsync()
    {
        _engine = PythonEngine.Create();
        await using (Py.GIL())
        {
            // Import pyama_core
            var pyama_core = Py.Import("pyama_core");
            _initialized = true;
        }
    }
    
    public async Task<T> ExecuteAsync<T>(string pythonCode)
    {
        await using (Py.GIL())
        {
            dynamic result = _engine.Eval(pythonCode);
            return result.As<T>();
        }
    }
}
```

### Data Model Interop

```csharp
// Models/MicroscopyMetadata.cs
public class MicroscopyMetadata
{
    public int NumberOfFovs { get; set; }
    public string[] ChannelNames { get; set; }
    public int[] Dimensions { get; set; }
    public float PixelSizeUm { get; set; }
    
    public static MicroscopyMetadata FromPython(PyObject pythonObj)
    {
        return new MicroscopyMetadata
        {
            NumberOfFovs = pythonObj.GetAttr("n_fovs").As<int>(),
            ChannelNames = pythonObj.GetAttr("channel_names").As<string[]>(),
            Dimensions = pythonObj.GetAttr("shape").As<int[]>(),
            PixelSizeUm = pythonObj.GetAttr("pixel_size_um").As<float>()
        };
    }
}
```

## Features

### 1. Processing Tab

**File Loading**
- Modern file picker with preview
- ND2/CZI file support
- Metadata extraction and display

**Channel Configuration**
- Drag-and-drop channel selection
- Real-time feature discovery from pyama-core
- Visual channel indicators

**Workflow Execution**
- Async workflow with progress indicators
- Real-time status updates
- Cancellation support

```razor
@page "/processing"
<EditForm Model="@workflowConfig" OnSubmit="StartWorkflow">
    <DataAnnotationsValidator />
    
    <MudForm @ref="processingForm">
        <MudFilePicker T="string" Label="ND2 File" 
                       @bind-Value="workflowConfig.FilePath" />
                       
        <MudSelect T="int" Label="Phase Contrast Channel" 
                   @bind-Value="workflowConfig.PhaseChannel">
            @foreach (var channel in availableChannels)
            {
                <MudSelectItem Value="@channel.Index">
                    @channel.Name
                </MudSelectItem>
            }
        </MudSelect>
        
        <MudCheckBox @bind-Checked="workflowConfig.ManualParams" 
                     Label="Set parameters manually" />
                     
        @if (workflowConfig.ManualParams)
        {
            <MudTextField @bind-Value="workflowConfig.FovStart" 
                          Label="FOV Start" />
            <MudTextField @bind-Value="workflowConfig.FovEnd" 
                          Label="FOV End" />
        }
        
        <MudButton Type="submit" Variant="Variant.Filled">
            Start Workflow
        </MudButton>
        
        @if (isRunning)
        {
            <MudProgressCircular />
            <MudText>@progressMessage</MudText>
            <MudButton OnClick="CancelWorkflow" Variant="Variant.Outlined">
                Cancel
            </MudButton>
        }
    </MudForm>
</EditForm>

@code {
    private WorkflowConfig workflowConfig = new();
    private bool isRunning;
    private string progressMessage;
    
    private async Task StartWorkflow()
    {
        isRunning = true;
        progressMessage = "Initializing workflow...";
        
        try
        {
            await pyamaService.RunWorkflowAsync(workflowConfig);
            Snackbar.Add("Workflow completed successfully", Severity.Success);
        }
        catch (Exception ex)
        {
            Snackbar.Add($"Workflow failed: {ex.Message}", Severity.Error);
        }
        finally
        {
            isRunning = false;
        }
    }
}
```

### 2. Visualization Tab (In Progress)

**Image Display**
- Multi-channel image viewer
- Frame navigation with controls
- Zoom and pan capabilities

**Trace Visualization**
- Real-time trace plotting
- Interactive trace selection
- Quality control markers

**Data Tables**
- Sortable trace listings
- Export to CSV/Excel
- Filter and search capabilities

### 3. Analysis Tab

**Model Configuration**
- Dynamic model selection from pyama-core
- Parameter bound configuration
- Visual parameter editor

**Fitting Execution**
- Parallel fitting progress
- Result visualization
- Parameter distribution analysis

## Python.NET Interop Details

### GIL Management

```csharp
public class PyamaCoreService
{
    private readonly PythonService _python;
    
    public PyamaCoreService(PythonService python)
    {
        _python = python;
    }
    
    public async Task<MicroscopyMetadata> LoadMetadataAsync(string filePath)
    {
        await using (Py.GIL())
        {
            dynamic io = Py.Import("pyama_core.io");
            dynamic metadata = io.load_microscopy_file(filePath);
            return MicroscopyMetadata.FromPython(metadata[1]);
        }
    }
    
    public async Task<string> StartWorkflowAsync(WorkflowConfig config)
    {
        return await _python.ExecuteAsync<string>($@"
import sys
sys.path.append('{config.PyamaCorePath}')
from pyama_core.processing.workflow import run_complete_workflow
from pyama_core.types.processing import ProcessingConfig, Channels, ChannelSelection

# Build configuration
processing_config = ProcessingConfig(
    output_dir='{config.OutputPath}',
    channels=Channels(
        pc=ChannelSelection(channel={config.PhaseChannel}, features={config.PhaseFeatures}),
        fl=[ChannelSelection(channel=c.channel, features=c.features) for c in config.FluorescenceChannels]
    ),
    params={{{ConvertParams(config.Parameters)}}
)

# Run workflow
success = run_complete_workflow(
    metadata=metadata,
    config=processing_config,
    fov_start={config.FovStart},
    fov_end={config.FovEnd},
    batch_size={config.BatchSize},
    n_workers={config.NumWorkers}
)
return str(success)
");
    }
}
```

### Type Conversion

```csharp
public static class PythonConverters
{
    public static PyObject ToPython(this WorkflowConfig config)
    {
        dynamic dict = new PyDict();
        dict["file_path"] = config.FilePath.ToPython();
        dict["output_dir"] = config.OutputPath.ToPython();
        dict["phase_channel"] = config.PhaseChannel.ToPython();
        return dict;
    }
    
    public static List<T> FromPythonList<T>(this PyObject obj)
    {
        var list = new List<T>();
        foreach (var item in obj)
        {
            list.Add(item.As<T>());
        }
        return list;
    }
}
```

## Distribution

### Build for Distribution

```bash
# Create self-contained build
dotnet publish -c Release -r win-x64 --self-contained

# Build with bundled Python
dotnet publish -c Release -r win-x64 /p:IncludePythonFiles=true
```

### Python Bundle

For standalone distribution, bundle Python environment:

```bash
# Download Python embeddable package
# Extract to PyamaBlazor/python/

# Install pyama-core into bundled Python
cd python
python.exe -m pip install --target=Lib/site-packages path/to/pyama-core

# Configure app to use bundled Python
# See Services/BundlePythonService.cs
```

## Performance Considerations

### GIL Usage

- Minimize time spent holding GIL
- Use async/await for I/O operations
- Batch operations when possible

```csharp
// Good: Release GIL during long operations
public async Task ProcessLargeDatasetAsync(string path)
{
    await using (Py.GIL())
    {
        // Acquire GIL only for initialization
        dynamic processor = Py.Import("my_processor");
    }
    
    // Long operation without GIL
    await Task.Run(() => /* heavy computation */);
    
    await using (Py.GIL())
    {
        // Get results without holding GIL too long
        var results = processor.get_results();
    }
}
```

### Memory Management

- Dispose of Python objects explicitly
- Use using statements for PyObject
- Monitor memory during large operations

## Testing

### Unit Tests

```csharp
[Test]
public async Task LoadMetadata_ReturnsExpectedData()
{
    // Arrange
    var service = new PyamaCoreService(_python);
    var testFile = Path.Combine(TestDataPath, "test.nd2");
    
    // Act
    var metadata = await service.LoadMetadataAsync(testFile);
    
    // Assert
    Assert.AreEqual(100, metadata.NumberOfFovs);
    Assert.AreEqual("Phase,GFP,RFP", string.Join(",", metadata.ChannelNames));
}
```

### Integration Tests

```csharp
[Test]
public async Task CompleteWorkflow_ProcessesSuccessfully()
{
    // Arrange
    var config = new WorkflowConfig
    {
        FilePath = TestND2File,
        OutputPath = TestOutputDir,
        PhaseChannel = 0,
        PhaseFeatures = new[] { "area", "aspect_ratio" }
    };
    
    // Act
    var result = await service.StartWorkflowAsync(config);
    
    // Assert
    Assert.IsTrue(result.Contains("completed successfully"));
    Assert.IsTrue(Directory.Exists(Path.Combine(TestOutputDir, "fov_000")));
}
```

## Future Roadmap

### Short Term (Q1 2024)
- Complete Visualization tab implementation
- Add support for Pyama-Air configuration
- Implement offline mode capability

### Medium Term (Q2 2024)
- Add cloud storage integration
- Support for additional file formats (Ome-Tiff)
- Real-time collaboration features

### Long Term (Q3 2024+)
- Multi-platform deployment (macOS, Linux)
- Advanced visualization with GPU acceleration
- Plugin system for custom workflows

## Troubleshooting

### Common Issues

**"Python engine failed to initialize":**
- Verify Python 3.11+ is installed
- Check pyama-core is in Python path
- Ensure Python.NET version compatibility

**"Workflow fails with import error":**
- Confirm pyama-core installation
- Check UV workspace is activated
- Verify PYTHONPATH includes pyama-core

**"UI freezes during long operations":**
- Ensure operations use async/await
- Check for GIL being held too long
- Verify background thread usage

### Debug Mode

```csharp
// Enable detailed logging
#if DEBUG
    logger.LogInformation("Python version: {0}", PythonEngine.Version);
    logger.LogInformation("Pyama-core path: {0}", pythonPath);
#endif

// Check Python environment
await using (Py.GIL())
{
    dynamic sys = Py.Import("sys");
    Console.WriteLine($"Python path: {sys.path}");
}
```

## Resources

- .NET MAUI documentation: https://docs.microsoft.com/dotnet/maui/
- Python.NET documentation: https://pythonnet.github.io/
- MudBlazor components: https://mudblazor.com/
- PyAMA core algorithms: [Workflow Pipeline](../reference/workflow-pipeline.md)

PyAMA-Blazor represents the next evolution of PyAMA's user interface, offering a modern, cross-platform experience while maintaining full compatibility with the proven pyama-core analysis engine.

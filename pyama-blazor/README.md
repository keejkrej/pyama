# PyAMA-Blazor

A .NET MAUI Blazor Hybrid desktop application for microscopy image analysis, designed as a replacement for PyAMA-Pro (Qt/Python).

## Architecture

PyAMA-Blazor uses Python.NET to directly interop with `pyama-core` for business logic, while providing a modern cross-platform UI with MudBlazor.

```
pyama-blazor/
├── PyamaBlazor/
│   ├── Components/
│   │   ├── Layout/          # MainLayout, NavMenu
│   │   └── Pages/           # Processing, Visualization, Analysis
│   ├── Models/              # C# data models
│   ├── Services/            # Python.NET interop services
│   └── wwwroot/             # Static assets
└── README.md
```

## Prerequisites

- .NET 10 SDK with MAUI workload
- Python 3.11+ with `pyama-core` installed
- Windows 10/11 (for initial development)

## Development Setup

1. Install MAUI workload:
```bash
dotnet workload install maui-windows
```

2. Ensure pyama-core is installed in your Python environment:
```bash
uv pip install -e ../pyama-core
```

3. Build and run:
```bash
cd PyamaBlazor
dotnet build
dotnet run
```

## Python Integration

The app uses Python.NET to call pyama-core directly. The `PythonService` handles:
- Python engine initialization
- GIL management for thread safety
- Type conversion between C# and Python

### Bundled Python (for distribution)

For standalone distribution, bundle Python embeddable package:

1. Download Python embeddable from python.org
2. Install pyama-core into it:
```bash
python -m pip install --target=python/Lib/site-packages ./pyama-core
```
3. Place in `PyamaBlazor/python/` folder

## Features

### Processing Tab
- Load ND2/CZI microscopy files
- Configure channels and features
- Run segmentation, tracking, extraction workflows

### Visualization Tab (WIP)
- FOV image display
- Trace plotting

### Analysis Tab
- Model fitting (maturation, trivial, etc.)
- Parameter configuration
- Results export

## Dependencies

- **MudBlazor** - Material Design UI components
- **Python.NET** - .NET/Python interop
- **pyama-core** - Core processing library

## License

MIT

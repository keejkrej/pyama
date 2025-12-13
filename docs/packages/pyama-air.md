# PyAMA-Air

PyAMA-Air provides both a modern GUI and a command-line interface for configuring and running PyAMA workflows without opening the full Qt application. It offers guided wizards for rapid workflow configuration and batch processing.

## Installation

```bash
# Install as part of the workspace
uv pip install -e pyama-air/
```

## Launching

### GUI Application
```bash
pyama-air gui
```

### Command Line Interface
```bash
pyama-air cli
Or directly:
pyama-air cli workflow
pyama-air cli merge
```

## GUI Features

### Main Interface
- Modern, clean interface with drag-and-drop support
- Tool menu for accessing wizards
- Recent configurations history
- System tray integration

### Workflow Wizard
Step-by-step configuration:

1. **Select ND2 File**: Browse and select microscopy file
2. **Configure Channels**: Select phase contrast and fluorescence channels
3. **Select Features**: Choose features to extract (automatically discovered)
4. **Set Output Directory**: Choose save location
5. **Configure Parameters**: FOV range, batch size, worker count
6. **Review Summary**: Check all settings
7. **Execute**: Start processing with progress tracking

### Merge Wizard
Combine processed results:

1. **Assign FOVs**: Add samples and ranges
2. **Select Directories**: Input and output folders
3. **Run Merge**: Combine into sample CSVs

## CLI Features

### Interactive Mode
```bash
pyama-air cli
```
Prompts through configuration options.

### Direct Commands

**Workflow Configuration:**
```bash
pyama-air cli workflow
```

Guides through:
1. ND2 file path
2. Phase contrast channel selection
3. Feature selection (comma-separated)
4. Fluorescence channel configuration
5. Output directory choice
6. FOV range specification
7. Batch processing settings

**Merge Operation:**
```bash
pyama-air cli merge
```

Guides through:
1. Sample definitions (name: range format)
2. Sample YAML file location
3. Input/output directories

### Help Commands
```bash
pyama-air --help
pyama-air cli --help
pyama-air cli workflow --help
pyama-air cli merge --help
pyama-air gui --help
```

## Key Features

### Dynamic Feature Discovery
- Automatically discovers available features from pyama-core
- No hardcoded feature lists
- Supports custom extensions
- Fallback to defaults if invalid features specified

### Real-time Validation
- Immediate feedback on configuration validity
- Clear error messages
- Automatic range checking
- FOV validation against loaded data

### Progress Indicators
- Visual progress bars in GUI
- Real-time status updates in CLI
- Cancellation support
- Estimated time remaining

### Configuration Export
- Save configurations for reuse
- Share with collaborators
- Template system for common setups
- Version control friendly YAML format

## Example Workflows

### Quick Test Run
```bash
# GUI method
1. Launch: pyama-air gui
2. Click "Workflow Wizard"
3. Select test ND2
4. Choose default settings
5. Set foV_end to 2 for quick test
6. Run with progress monitoring

# CLI method
pyama-air cli workflow
# Follow prompts, use small FOV range
```

### Batch Processing
```bash
# Save configuration template
pyama-air cli workflow > config_template.txt
# Edit parameters as needed
# Use with pyama-air cli --config config.txt
```

### Automated Merge
```bash
# Create samples.yaml manually or via GUI
echo "sample1: 0-4" > samples.yaml
echo "sample2: 5-9" >> samples.yaml

pyama-air cli merge --input /path/to/processed --output /path/to/merged
```

## Configuration Format

### Sample YAML
```yaml
samples:
  - name: control
    fovs: "0-9"
  - name: treatment
    fovs: "10-19"
  - name: reference
    fovs: "95-99"
```

### Workflow Config (JSON saved by GUI)
```json
{
  "nd2_path": "/path/to/data.nd2",
  "phase_channel": 0,
  "phase_features": ["area", "aspect_ratio"],
  "fluorescence_channels": [
    {"channel": 1, "features": ["intensity_total"]}
  ],
  "output_dir": "/path/to/output",
  "fov_start": 0,
  "fov_end": -1,
  "batch_size": 2,
  "n_workers": 2
}
```

## Integration

### With PyAMA-Pro
- Use Air for rapid prototyping
- Export configurations to PyAMA-Pro
- Compatible output formats
- Seamless data exchange

### With PyAMA-Core
- Direct API access
- Plugin system integration
- Custom feature discovery
- Batch processing capabilities

### External Automation
- Scriptable via CLI
- JSON/YAML configuration support
- Return codes for automation
- Logging integration

## Performance Tips

### GUI Optimization
- Use SSD for ND2 files
- Close unnecessary tabs during processing
- Monitor memory usage with large datasets

### CLI Optimization
- piping: `echo "input" | pyama-air cli workflow`
- Use absolute paths in non-interactive mode
- Combine with GNU parallel for multiple runs

## Error Handling

### Common Issues
- **File not found**: Check paths and permissions
- **Channel out of range**: Verify ND2 metadata
- **Invalid features**: Use --list-features to check
- **Export failures**: Ensure write permissions

### Recovery
- Autosave of configurations
- Partial result preservation
- Retry mechanisms for network storage
- Resume capability for interrupted jobs

## Extending PyAMA-Air

### Adding Wizards
- Inherit from BaseWizard class
- Implement validate() method
- Register in main window
- Add to tools menu

### CLI Extensions
- Create new subcommand in cli/
- Implement callback function
- Add to command parser
- Update help text

### Custom Validators
- Create validator functions
- Register with configuration schema
- Provide clear error messages
- Testing frameworks included

## Development
```bash
# Install dev dependencies
uv sync --all-extras

# Run in development mode
python -m pyama_air.gui
python -m pyama_air.cli

# Run tests
pytest tests/pyama_air/
```

## Next Steps

- See [Processing Tab Guide](../user-guide/processing-tab.md) for detailed workflow parameters
- Check [Merge Workflow](../user-guide/merge-workflow.md) for sample organization
- Visit [Workflow Pipeline](../reference/workflow-pipeline.md) for technical details

PyAMA-Air provides a lightweight alternative to the full PyAMA-Pro GUI, perfect for: 
- Quick parameter testing
- Batch processing automation
- Headless server workflows
- Integration into pipelines

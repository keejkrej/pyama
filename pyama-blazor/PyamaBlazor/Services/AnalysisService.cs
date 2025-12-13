using Python.Runtime;
using PyamaBlazor.Models;

namespace PyamaBlazor.Services;

public class AnalysisService : IAnalysisService
{
    private readonly IPythonService _python;

    public AnalysisService(IPythonService python)
    {
        _python = python;
    }

    public async Task<List<string>> GetAvailableModels()
    {
        return await _python.RunAsync(() =>
        {
            dynamic models = Py.Import("pyama_core.analysis.models");
            var result = models.list_models();
            return ((IEnumerable<dynamic>)result).Select(x => (string)x).ToList();
        });
    }

    public async Task<ModelInfo?> GetModelInfo(string modelName)
    {
        return await _python.RunAsync(() =>
        {
            dynamic models = Py.Import("pyama_core.analysis.models");
            dynamic model = models.get_model(modelName);

            var info = new ModelInfo
            {
                Name = modelName,
                Description = (string)(model.__doc__ ?? ""),
            };

            // Extract default fit parameters
            var defaultFit = model.DEFAULT_FIT;
            foreach (var key in defaultFit.Keys())
            {
                var param = defaultFit[(string)key];
                info.DefaultParameters.Add(new FitParameter
                {
                    Name = (string)key,
                    Value = (double)param.value,
                    LowerBound = (double)param.lb,
                    UpperBound = (double)param.ub,
                    IsFixed = false,
                });
            }

            // Extract default fixed parameters
            var defaultFixed = model.DEFAULT_FIXED;
            foreach (var key in defaultFixed.Keys())
            {
                info.DefaultFixedParameters.Add(new FitParameter
                {
                    Name = (string)key,
                    Value = (double)defaultFixed[(string)key],
                    IsFixed = true,
                });
            }

            return info;
        });
    }

    public async Task<FittingSummary> RunFittingAsync(
        FittingConfig config,
        IProgress<JobProgress>? progress = null,
        CancellationToken ct = default)
    {
        return await _python.RunAsync(() =>
        {
            dynamic fitting = Py.Import("pyama_core.analysis.fitting_service");
            dynamic models = Py.Import("pyama_core.analysis.models");

            // Get model
            dynamic model = models.get_model(config.ModelType);

            // Build fit params dict
            var fitParams = new PyDict();
            foreach (var p in config.FitParameters)
            {
                dynamic types = Py.Import("pyama_core.analysis.models.base");
                var param = types.FitParam(
                    value: p.Value,
                    lb: p.LowerBound,
                    ub: p.UpperBound);
                fitParams[p.Name] = param;
            }

            // Build fixed params dict
            var fixedParams = new PyDict();
            foreach (var p in config.FixedParameters)
            {
                fixedParams[p.Name] = p.Value.ToPython();
            }

            // Run fitting service
            var result = fitting.run_fitting_service(
                csv_path: config.CsvPath,
                model: model,
                fit_params: fitParams,
                fixed_params: fixedParams,
                frame_interval: config.FrameInterval);

            return new FittingSummary
            {
                TotalCells = (int)result["total_cells"],
                SuccessfulFits = (int)result["successful_fits"],
                FailedFits = (int)result["failed_fits"],
                MeanRSquared = (double)result["mean_r_squared"],
                OutputPath = (string)result["output_path"],
            };
        });
    }
}

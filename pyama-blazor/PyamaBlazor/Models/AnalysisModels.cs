namespace PyamaBlazor.Models;

public class FitParameter
{
    public string Name { get; set; } = string.Empty;
    public double Value { get; set; }
    public double LowerBound { get; set; }
    public double UpperBound { get; set; }
    public bool IsFixed { get; set; }
}

public class ModelInfo
{
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public List<FitParameter> DefaultParameters { get; set; } = [];
    public List<FitParameter> DefaultFixedParameters { get; set; } = [];
}

public class FittingResult
{
    public int Fov { get; set; }
    public int Cell { get; set; }
    public string ModelType { get; set; } = string.Empty;
    public bool Success { get; set; }
    public double RSquared { get; set; }
    public Dictionary<string, double> FittedParams { get; set; } = [];
}

public class FittingConfig
{
    public string CsvPath { get; set; } = string.Empty;
    public string ModelType { get; set; } = string.Empty;
    public List<FitParameter> FitParameters { get; set; } = [];
    public List<FitParameter> FixedParameters { get; set; } = [];
    public double FrameInterval { get; set; } = 1.0;
}

public class FittingSummary
{
    public int TotalCells { get; set; }
    public int SuccessfulFits { get; set; }
    public int FailedFits { get; set; }
    public double MeanRSquared { get; set; }
    public string OutputPath { get; set; } = string.Empty;
}

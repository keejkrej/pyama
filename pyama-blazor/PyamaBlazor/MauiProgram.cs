using CommunityToolkit.Maui;
using CommunityToolkit.Maui.Storage;
using Microsoft.Extensions.Logging;
using MudBlazor.Services;
using PyamaBlazor.Services;

namespace PyamaBlazor;

public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        var builder = MauiApp.CreateBuilder();
        builder
            .UseMauiApp<App>()
            .UseMauiCommunityToolkit()
            .ConfigureFonts(fonts =>
            {
                fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
            });

        builder.Services.AddMauiBlazorWebView();
        builder.Services.AddMudServices();

        // Register Python interop services
        builder.Services.AddSingleton<IPythonService, PythonService>();
        builder.Services.AddSingleton<IProcessingService, ProcessingService>();
        builder.Services.AddSingleton<IAnalysisService, AnalysisService>();

        // Register CommunityToolkit services
        builder.Services.AddSingleton(FolderPicker.Default);

#if DEBUG
        builder.Services.AddBlazorWebViewDeveloperTools();
        builder.Logging.AddDebug();
#endif

        return builder.Build();
    }
}

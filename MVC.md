# PyAMA-Qt MVC Architecture

This document summarizes the strict PySide6 MVC pattern followed by the PyAMA-Qt
application after the recent refactor.

## Core Principle

**The main window is responsible for creating all instances and injecting dependencies.**

## Guiding Rules

1. **Signal Direction**

   - **View → Controller:** Qt signals only (e.g., button clicks, selections).
   - **Controller → Model:** Direct method/property calls on models.
   - **Model → Controller:** Qt signals emitted by models.
   - **Controller → View:** Direct method calls on widgets or view helpers.

2. **Component Responsibilities**

   - **Models**
     - Expose imperative setters/getters.
     - Emit signals when state changes.
     - Never reference controllers or views.
     - Never receive Qt signals.
   - **Views**
     - Contain UI widgets and layout code.
     - Emit signals describing user intent.
     - Offer idempotent setters for controllers to bind data.
     - Never call models or controllers directly.
   - **Controllers**
     - Receive injected view and model references from main window.
     - Connect all signals in `__init__`.
     - Translate view events into model updates and vice versa.
     - Handle long-running work via background workers; capture worker signals,
       update models, and relay status back to the view.
     - Do **not** define/emit custom signals; state is expressed via model/view APIs.
     - **Must not** create their own models or views.

3. **Main Window Responsibilities**
   - **Only** component that creates instances of models, views, and controllers.
   - Creates models first, then views, then controllers with injected dependencies.
   - Ensures proper dependency injection into controllers.

## Controller Constructor Pattern

All controllers **must** follow this constructor pattern:

```python
class SomeController(QObject):
    def __init__(self, view: SomePage, model: SomeModel) -> None:
        super().__init__()
        self._view = view
        self._model = model

        self._connect_view_signals()
        self._connect_model_signals()
        self._initialise_view_state()
```

**Requirements:**

- Controllers **must not** create their own models or views
- Controllers **must** accept both view and model as constructor arguments
- Controllers **must** store references as `self._view` and `self._model`

Key points:

- `_connect_view_signals()` hooks widget signals to controller handlers.
- `_connect_model_signals()` relays model changes back to view methods.
- View setters expose only the data needed for rendering; they remain unaware of model classes.
- Controllers store no transient Qt state on views; everything is persisted via models or simple
  controller attributes.

## Main Window Implementation

The `MainWindow` class (`views/main_window.py`) implements the dependency injection pattern:

```python
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        # 1. Create models first
        self.analysis_model = AnalysisModel()
        self.processing_model = ProcessingModel()
        self.visualization_model = VisualizationModel()

        # 2. Create views
        self.processing_page = ProcessingPage(self)
        self.analysis_page = AnalysisPage(self)
        self.visualization_page = VisualizationPage(self)

        # 3. Create controllers with injected dependencies
        self.processing_controller = ProcessingController(
            self.processing_page, self.processing_model
        )
        self.analysis_controller = AnalysisController(
            self.analysis_page, self.analysis_model
        )
        self.visualization_controller = VisualizationController(
            self.visualization_page, self.visualization_model
        )
```

## Dependency Flow

```
MainWindow
├── Creates: AnalysisModel
├── Creates: AnalysisPage
└── Creates: AnalysisController(AnalysisPage, AnalysisModel)
    ├── Uses: self._view (AnalysisPage)
    └── Uses: self._model (AnalysisModel)
```

## Controller Details

### Analysis Controller (`controllers/analysis.py`)

- Receives injected `AnalysisModel` containing `AnalysisDataModel`, `FittingModel`, `FittedResultsModel`.
- Handles CSV loading, fitting requests, worker progress, and plot rendering.
- Calls out to the view panels (`AnalysisDataPanel`, `AnalysisFittingPanel`, `AnalysisResultsPanel`)
  via dedicated setter methods.

### Processing Controller (`controllers/processing.py`)

- Receives injected `ProcessingModel` containing `ProcessingConfigModel` and `WorkflowStatusModel`.
- Coordinates the workflow configuration, launch, and merge operations.
- Drives `ProcessingConfigPanel` and `ProcessingMergePanel` using plain data payloads.
- Background workers update models and cascaded view state.

### Visualization Controller (`controllers/visualization.py`)

- Receives injected `VisualizationModel` containing `ProjectModel`, `ImageCacheModel`, `TraceTableModel`, `TraceFeatureModel`, and `TraceSelectionModel`.
- Manages project discovery, FOV loading, image display, and trace inspection.
- Responds to view events (`project_load_requested`, data type selection, trace toggles) and
  updates the corresponding models/views directly.

## View Expectations

Every view/panel class exports the minimum surface for controllers:

- Signals describing user actions (`csv_selected`, `fit_requested`, `merge_requested`, etc.).
- Methods to receive controller updates (`render_plot`, `set_parameter_defaults`,
  `set_available_data_types`, `set_trace_dataset`, etc.).

Views never:

- Instantiate or mutate models.
- Emit signals in response to model changes.
- Store references to controllers.

## Background Workers

Long-running tasks (e.g., CSV fitting, ND2 loading, visualization preprocessing) are implemented as
QObject workers:

- Emit status/error/finished signals.
- Controllers connect worker signals to private handlers.
- Controllers manage worker lifecycle (`start_worker`, stop/cancel logic).

Workers **are** allowed to emit signals because they operate in isolation threads/processes,
but controllers are the only consumers of those signals.

## Anti-Patterns to Avoid

❌ **Don't** create models inside controllers:

```python
# WRONG
class AnalysisController(QObject):
    def __init__(self, view: AnalysisPage) -> None:
        self._data_model = AnalysisDataModel()  # ❌ Don't do this
```

❌ **Don't** create views inside controllers:

```python
# WRONG
class AnalysisController(QObject):
    def __init__(self) -> None:
        self._view = AnalysisPage()  # ❌ Don't do this
```

❌ **Don't** access models directly from views:

```python
# WRONG
class AnalysisPage(QWidget):
    def some_method(self):
        model = AnalysisModel()  # ❌ Don't do this
```

## Benefits

1. **Testability**: Controllers can be easily unit tested with mock views and models
2. **Flexibility**: Different model implementations can be injected without changing controllers
3. **Separation of Concerns**: Each component has a single responsibility
4. **Maintainability**: Clear dependencies make the codebase easier to understand and modify

## Summary

The architecture enforces a single direction of dependency with proper dependency injection:

```
MainWindow creates all instances
├── Models (business logic)
├── Views (UI components)
└── Controllers (coordination)
    ├── View --signals--> Controller --methods--> Model
    └── Model --signals--> Controller --methods--> View
```

This guarantees predictable data flow, simplifies testing, and keeps the Qt widgets free from
business logic while ensuring proper separation of concerns through dependency injection.

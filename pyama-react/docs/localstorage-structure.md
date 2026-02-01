# localStorage Data Structure

This document describes the data structure used by pyama-react's localStorage.

## Overview

pyama-react uses Zustand's `persist` middleware to automatically save and restore application state to localStorage. All data is stored as JSON strings.

## Storage Keys

The application uses the following localStorage keys:

### Zustand Store Keys (with persist middleware)

1. **`pyama:processing`** - Processing tab state
2. **`pyama:analysis`** - Analysis tab state  
3. **`pyama:visualization`** - Visualization tab state
4. **`pyama:chat`** - Chat tab state (if persisted)

### Direct localStorage Keys

5. **`pyama_current_task_id`** - Current processing task ID (string, not JSON)

### Theme Keys (managed by theme system)

6. **Theme-related keys** - Managed by `apply-theme.ts` (not part of Zustand stores)

## Zustand Persist Format

Zustand's persist middleware stores data in the following format:

```json
{
  "state": {
    // ... persisted state fields ...
  },
  "version": 0
}
```

**Note**: The `version` field is optional and only present if a version is specified in the persist configuration. If no version is specified, the format may be just the state object directly.

### Example: `pyama:processing`

```json
{
  "state": {
    "microscopyFile": "/path/to/file.nd2",
    "microscopyMetadata": {
      "n_fov": 10,
      "n_frames": 100,
      "channels": { ... },
      // ... other metadata fields
    },
    "pcEntries": [
      { "channel": 0, "feature": "area" }
    ],
    "flEntries": [
      { "channel": 1, "feature": "intensity_total" }
    ],
    "availableFeatures": {
      "phase_contrast": ["area", "circularity"],
      "fluorescence": ["intensity_total", "particle_num"]
    },
    "outputDir": "/path/to/output",
    "manualParams": true,
    "params": {
      "segmentation_threshold": 0.5,
      "tracking_iou_threshold": 0.3
    },
    "paramsSchema": {
      "segmentation_threshold": {
        "type": "number",
        "default": 0.5,
        "description": "Threshold for segmentation"
      }
    }
  },
  "version": 0
}
```

### Example: `pyama:visualization`

```json
{
  "state": {
    "dataFolder": "/path/to/project",
    "fov": 0,
    "selectedFeature": "intensity_total_ch_1",
    "currentPage": 0
  },
  "version": 0
}
```

### Example: `pyama:analysis`

```json
{
  "state": {
    "dataFolder": "/path/to/data",
    "frameInterval": 10
  },
  "version": 0
}
```

### Example: `pyama:chat`

```json
{
  "state": {
    "items": [
      {
        "type": "message",
        "data": {
          "id": "uuid",
          "role": "user",
          "content": "Hello"
        }
      }
    ],
    "isProcessing": false,
    "error": null,
    "pendingTools": {}
  },
  "version": 0
}
```

## Direct localStorage Values

### `pyama_current_task_id`

Stored as a plain string (not JSON):

```
"task-uuid-12345"
```

## Partial Persistence

Zustand stores use the `partialize` option to only persist specific fields:

- **Processing Store**: Persists `microscopyFile`, `microscopyMetadata`, `pcEntries`, `flEntries`, `availableFeatures`, `outputDir`, `manualParams`, `params`, `paramsSchema`
  - Does NOT persist: `metadataLoading`, `featuresLoading`, `schemaLoading` (loading states)

- **Visualization Store**: Persists `dataFolder`, `fov`, `selectedFeature`, `currentPage`
  - Does NOT persist: `projectData`, `traces`, `totalTraces`, `availableFeatures`, `loading`, `error`, `qualityUpdates` (runtime data)

- **Analysis Store**: Persists `dataFolder`, `frameInterval`
  - All fields are persisted (no exclusions)

- **Chat Store**: May persist conversation history (check store implementation)

## Storage Lifecycle

1. **On App Start**: All localStorage keys are cleared via `clear-storage-init.ts`
2. **Store Creation**: Zustand stores are created and attempt to restore from localStorage (which is now empty, so defaults are used)
3. **Explicit Reset**: `initializeStorage()` explicitly resets all stores to initial state
4. **During Use**: As users interact with the app, Zustand automatically persists state changes to localStorage
5. **On Next Start**: Process repeats - localStorage is cleared again

## Accessing localStorage Data

### In Browser DevTools

```javascript
// View all PyAMA keys
Object.keys(localStorage).filter(k => k.startsWith('pyama'))

// View a specific store
JSON.parse(localStorage.getItem('pyama:processing'))

// View task ID
localStorage.getItem('pyama_current_task_id')
```

### Programmatically

```typescript
// Read store data
const data = localStorage.getItem('pyama:processing');
const parsed = JSON.parse(data || '{}');
const state = parsed.state || parsed; // Handle both formats

// Read task ID
const taskId = localStorage.getItem('pyama_current_task_id');
```

## Migration Notes

The code in `storage.ts` handles both formats:
- `{ state: {...}, version: 0 }` (with wrapper)
- `{ ... }` (direct state object)

This is done via: `const state = parsed.state || parsed;`

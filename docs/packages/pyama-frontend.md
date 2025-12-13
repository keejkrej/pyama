# PyAMA-Frontend

PyAMA-Frontend is a modern Next.js web application that provides a browser-based interface for microscopy image analysis. It communicates with the PyAMA Backend REST API to deliver a full-featured web experience for PyAMA workflows.

## Technology Stack

- **Framework**: Next.js 13+ with App Router
- **UI Components**: Tailwind CSS and shadcn/ui components  
- **State Management**: React hooks and context
- **API Client**: Fetch API with TypeScript types
- **Type Safety**: Full TypeScript implementation

## Local Development

### Prerequisites
- Node.js 18+ 
- npm, yarn, pnpm, or bun
- PyAMA Backend server running

### Setup and Run

```bash
# Install dependencies
npm install
# or yarn install, pnpm install, bun install

# Start development server
npm run dev
# or yarn dev, pnpm dev, bun dev

# Application runs at http://localhost:3000
```

### Environment Configuration

Create `.env.local`:
```bash
# API base URL for PyAMA Backend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Optional: WebSocket URL for real-time updates
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

## Project Structure

```
pyama-frontend/
├── src/
│   ├── app/                     # Next.js App Router
│   │   ├── (dashboard)/         # Router groups
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── test/               # Development test pages
│   ├── components/              # React components
│   │   ├── ui/                 # shadcn/ui components
│   │   ├── forms/              # Form components
│   │   └── layout/             # Layout components
│   ├── lib/                    # Utility libraries
│   │   ├── api.ts              # API client functions
│   │   ├── types.ts            # TypeScript types
│   │   └── utils.ts            # Helper functions
│   └── types/                  # TypeScript type definitions
├── public/                     # Static assets
├── tailwind.config.js          # Tailwind CSS config
└── package.json
```

## Features Overview

### 1. File Browser
- Navigate local directories (via backend)
- Filter by file type (.nd2, .czi)
- Preview metadata for microscopy files
- Search functionality with patterns

### 2. Processing Workflow
- Load and configure microscopy files
- Channel and feature selection
- Parameter configuration
- Job submission and monitoring
- Real-time progress updates

### 3. Visualization
- Image viewing with channel selection
- Frame navigation controls
- Trace inspection interface
- Quality control markers

### 4. Analysis Dashboard
- Trace loading and visualization
- Model configuration
- Fitting results display
- Parameter analysis plots

### 5. Job Management
- Active job monitoring
- Job history
- Cancel and restart capabilities
- Status notifications

## Core Components

### API Client (`lib/api.ts`)

Typed API client for backend communication:

```typescript
// File operations
export async function loadMetadata(filePath: string) {
  const response = await fetch(`${API_URL}/processing/load-metadata`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath })
  });
  return response.json();
}

// Job management
export async function startWorkflow(config: WorkflowConfig) {
  const response = await fetch(`${API_URL}/processing/workflow/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return response.json();
}

// Status polling
export async function getJobStatus(jobId: string) {
  const response = await fetch(`${API_URL}/processing/workflow/status/${jobId}`);
  return response.json();
}
```

### File Browser Component

Advanced file explorer with microscopy support:

```typescript
export function FileBrowser({ onSelect, filters }: FileBrowserProps) {
  const [path, setPath] = useState('/');
  const [items, setItems] = useState<FileItem[]>([]);
  
  const handleDirectoryChange = async (newPath: string) => {
    const response = await listDirectory(newPath);
    setItems(response.items);
    setPath(newPath);
  };
  
  return (
    <div className="border rounded-lg">
      {/* Path breadcrumbs */}
      <Breadcrumb path={path} onChange={handleDirectoryChange} />
      
      {/* File list */}
      <div className="divide-y">
        {items.map(item => (
          <FileItem
            key={item.path}
            item={item}
            onClick={() => item.isDirectory ? handleDirectoryChange(item.path) : onSelect(item)}
          />
        ))}
      </div>
    </div>
  );
}
```

### Progress Monitor Component

Real-time job progress tracking:

```typescript
export function ProgressMonitor({ jobId, onComplete }: ProgressMonitorProps) {
  const [progress, setProgress] = useState<JobStatus | null>(null);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const status = await getJobStatus(jobId);
      setProgress(status);
      
      if (status.status === 'completed' || status.status === 'failed') {
        clearInterval(interval);
        onComplete(status);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [jobId, onComplete]);
  
  if (!progress) return <div>Loading...</div>;
  
  return (
    <div className="space-y-2">
      <ProgressBar value={progress.progress?.percentage || 0} />
      <p className="text-sm text-muted-foreground">{progress.message}</p>
    </div>
  );
}
```

## State Management

### React Context for Application State

```typescript
// App context for global state
interface AppContextType {
  selectedFile: MicroscopyFile | null;
  selectedChannels: ChannelConfig;
  jobs: Map<string, JobStatus>;
  notifications: Notification[];
}

export const AppContext = createContext<AppContextType | null>(null);

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
}
```

### Local Component State

```typescript
// Component-specific state
export function WorkflowForm() {
  const [config, setConfig] = useState<WorkflowConfig>(defaultConfig);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    
    try {
      await startWorkflow(config);
      showNotification('Workflow started successfully', 'success');
    } catch (error) {
      setErrors(formatErrors(error));
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
    </form>
  );
}
```

## Page Structure

### Main Dashboard (`app/page.tsx`)

```typescript
export default function Dashboard() {
  const { jobs, notifications } = useApp();
  
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <ProcessingWorkflow />
      </div>
      <div className="space-y-6">
        <ActiveJobs jobs={Array.from(jobs.values())} />
        <Notifications items={notifications} />
      </div>
    </div>
  );
}
```

### Test Pages (`app/test/`)

Each test page follows the pattern:

```typescript
export default function TestMerge() {
  return (
    <div className="container p-3 bg-muted rounded-lg border">
      <div className="text-xs font-medium text-muted-foreground mb-2">
        Testing Endpoints:
      </div>
      <div className="space-y-1 text-sm">
        <div>
          •{" "}
          <code className="bg-background px-2 py-1 rounded border">
            POST /api/v1/processing/merge
          </code>
        </div>
        <div>
          •{" "}
          <code className="bg-background px-2 py-1 rounded border">
            GET /api/v1/processing/features
          </code>
        </div>
      </div>
    </div>
  );
}
```

## API Integration

### Type Definitions

```typescript
// lib/types.ts
export interface WorkflowConfig {
  microscopy_path: string;
  output_dir: string;
  channels: Channels;
  parameters: ProcessingParameters;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress?: ProgressInfo;
  message: string;
}

export interface MicroscopyMetadata {
  n_fovs: number;
  n_frames: number;
  n_channels: number;
  channel_names: string[];
  time_units: string;
  pixel_size_um: number;
}
```

### Error Handling

```typescript
// lib/api.ts
export async function apiRequest<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      ...options
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new ApiError(error.error, error.error_code);
    }
    
    return response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error('Network error occurred');
  }
}

// Usage in components
try {
  const result = await apiRequest('/processing/workflow/start', {
    method: 'POST',
    body: JSON.stringify(config)
  });
} catch (error) {
  if (error.error_code === 'INVALID_PARAMETERS') {
    // Handle validation errors
    setFieldErrors(error.details);
  } else {
    // Handle other errors
    showNotification(error.message, 'error');
  }
}
```

## Responsive Design

### Tailwind CSS Breakpoints

```typescript
// Responsive layouts
export function ResponsiveGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {children}
    </div>
  );
}

// Mobile-friendly interfaces
export function MobileMenu() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="icon" className="md:hidden">
          <Menu className="h-4 w-4" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-80">
        <Navigation />
      </SheetContent>
    </Sheet>
  );
}
```

### Component Variants

```typescript
// Component variations for different screen sizes
export function WorkflowConfig() {
  return (
    <>
      {/* Desktop view */}
      <div className="hidden md:block">
        <ThreeColumnLayout />
      </div>
      
      {/* Mobile view */}
      <div className="md:hidden">
        <TabbedLayout />
      </div>
    </>
  );
}
```

## Performance Optimizations

### React Optimizations

```typescript
// Memo expensive computations
const ExpensiveComponent = memo(function ExpensiveComponent({ data }: Props) {
  const processed = useMemo(() => heavyComputation(data), [data]);
  return <div>{processed}</div>;
});

// Cache API calls
const useSWR = (key: string, fetcher: Function) => {
  // Use React Query or SWR for data fetching
};
```

### Image Loading

```typescript
// Lazy loading for large images
export function ImageViewer({ src, alt }: ImageProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsLoaded(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 }
    );
    
    if (imgRef.current) observer.observe(imgRef.current);
    
    return () => observer.disconnect();
  }, []);
  
  return (
    <div ref={imgRef}>
      {isLoaded && <img src={src} alt={alt} />}
      {!isLoaded && <div className="animate-pulse bg-gray-200 h-64" />}
    </div>
  );
}
```

## Testing

### Unit Tests with Jest

```typescript
// __tests__/api.test.ts
describe('API Client', () => {
  test('loadMetadata returns correct shape', async () => {
    const mockData = { n_fovs: 10, n_channels: 3 };
    
    fetchMock.mockResponseOnce(JSON.stringify({ success: true, data: mockData }));
    
    const result = await loadMetadata('/test.nd2');
    
    expect(result.n_fovs).toBe(10);
    expect(result.n_channels).toBe(3);
  });
});
```

### E2E Tests with Playwright

```typescript
// e2e/workflow.spec.ts
test('complete workflow execution', async ({ page }) => {
  await page.goto('/');
  
  // Select file
  await page.click('[data-testid="file-browser"]');
  await page.click('text=test.nd2');
  
  // Configure channels
  await page.selectOption('#phase-channel', '0');
  await page.selectOption('#phase-features', ['area', 'aspect_ratio']);
  
  // Run workflow
  await page.click('text=Start Workflow');
  
  // Verify completion
  await expect(page.locator('text=Job completed')).toBeVisible();
});
```

## Deployment

### Static Export (Vercel/Netlify)

```bash
# Build static version
npm run build
npm run export

# Deploy to Vercel
vercel --prod
```

### Full SSR Deployment

```bash
# Next.js deployment
npm run build
npm start

# Docker deployment
docker build -t pyama-frontend .
docker run -p 3000:3000 pyama-frontend
```

## Next Steps

- Implement WebSocket for real-time updates
- Add offline capabilities with service workers
- Integrate with cloud storage providers
- Add collaborative features
- Implement advanced visualizations

PyAMA-Frontend provides a modern, accessible interface for microscopy analysis that can be deployed anywhere, from local development to cloud production environments.

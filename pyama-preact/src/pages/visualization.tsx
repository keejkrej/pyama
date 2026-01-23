import { useState } from 'preact/hooks';
import { Card, Button } from '../components/ui';
import { ImageViewer } from '../components/popups/image-viewer';

interface VisualizationPageProps {
  path?: string;
}

export function VisualizationPage(_props: VisualizationPageProps) {
  const [isViewerOpen, setIsViewerOpen] = useState(false);

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-4">Visualization</h1>

      <div className="flex gap-4">
        {/* Load Card - 1/3 width */}
        <Card title="Load" className="flex-1">
          <div className="text-gray-500 dark:text-gray-400 text-center py-8">
            <p className="mb-2">Load panel placeholder</p>
            <p className="text-sm mb-4">Load processed results and select FOVs for visualization.</p>
            <Button onClick={() => setIsViewerOpen(true)}>
              Open Viewer
            </Button>
          </div>
        </Card>

        {/* Trace Card - 2/3 width */}
        <Card title="Trace" className="flex-[2]">
          <div className="text-gray-500 dark:text-gray-400 text-center py-8">
            <p className="mb-2">Trace panel placeholder</p>
            <p className="text-sm">View and annotate cell traces, mark quality flags.</p>
          </div>
        </Card>
      </div>

      {/* Image Viewer Popup */}
      <ImageViewer isOpen={isViewerOpen} onClose={() => setIsViewerOpen(false)} />
    </div>
  );
}

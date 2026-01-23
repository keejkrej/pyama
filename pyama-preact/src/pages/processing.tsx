import { Card } from '../components/ui';

interface ProcessingPageProps {
  path?: string;
}

export function ProcessingPage(_props: ProcessingPageProps) {
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-4">Processing</h1>

      <div className="flex gap-4">
        {/* Workflow Card - 2/3 width */}
        <Card title="Workflow" className="flex-[2]">
          <div className="text-gray-500 dark:text-gray-400 text-center py-8">
            <p className="mb-2">Workflow panel placeholder</p>
            <p className="text-sm">Load microscopy files, configure processing parameters, and run the workflow pipeline.</p>
          </div>
        </Card>

        {/* Merge Card - 1/3 width */}
        <Card title="Merge" className="flex-1">
          <div className="text-gray-500 dark:text-gray-400 text-center py-8">
            <p className="mb-2">Merge panel placeholder</p>
            <p className="text-sm">Combine processed FOV results into sample-level data.</p>
          </div>
        </Card>
      </div>
    </div>
  );
}

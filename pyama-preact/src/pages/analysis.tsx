import { useState } from 'preact/hooks';
import { Card, Button } from '../components/ui';
import { AnalysisWindow } from '../components/popups/analysis-window';

interface AnalysisPageProps {
  path?: string;
}

export function AnalysisPage(_props: AnalysisPageProps) {
  const [isAnalysisOpen, setIsAnalysisOpen] = useState(false);

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-4">Analysis</h1>

      <div className="flex gap-4">
        {/* Comparison Card - full width */}
        <Card title="Comparison" className="flex-1">
          <div className="text-gray-500 dark:text-gray-400 text-center py-8">
            <p className="mb-2">Comparison panel placeholder</p>
            <p className="text-sm mb-4">Load and compare analysis results from multiple samples.</p>
            <Button onClick={() => setIsAnalysisOpen(true)}>
              Open Analysis
            </Button>
          </div>
        </Card>
      </div>

      {/* Analysis Window Popup */}
      <AnalysisWindow isOpen={isAnalysisOpen} onClose={() => setIsAnalysisOpen(false)} />
    </div>
  );
}

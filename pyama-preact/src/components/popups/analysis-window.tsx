import { Modal, Card } from '../ui';

interface AnalysisWindowProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AnalysisWindow({ isOpen, onClose }: AnalysisWindowProps) {
  return (
    <Modal title="Analysis Window" isOpen={isOpen} onClose={onClose}>
      <div className="flex gap-4 h-full">
        {/* Data Panel */}
        <Card title="Data" className="flex-1">
          <div className="flex items-center justify-center h-full min-h-[300px] text-gray-500 dark:text-gray-400">
            <div className="text-center">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="font-medium mb-1">Data Panel</p>
              <p className="text-sm">Load trace data and configure fitting.</p>
            </div>
          </div>
        </Card>

        {/* Quality Panel */}
        <Card title="Quality" className="flex-1">
          <div className="flex items-center justify-center h-full min-h-[300px] text-gray-500 dark:text-gray-400">
            <div className="text-center">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="font-medium mb-1">Quality Panel</p>
              <p className="text-sm">Review fitting quality and metrics.</p>
            </div>
          </div>
        </Card>

        {/* Parameter Panel */}
        <Card title="Parameter" className="flex-1">
          <div className="flex items-center justify-center h-full min-h-[300px] text-gray-500 dark:text-gray-400">
            <div className="text-center">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
              </svg>
              <p className="font-medium mb-1">Parameter Panel</p>
              <p className="text-sm">View parameter distributions.</p>
            </div>
          </div>
        </Card>
      </div>
    </Modal>
  );
}

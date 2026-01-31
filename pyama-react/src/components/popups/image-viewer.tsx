import { Modal, Card } from "../ui";

interface ImageViewerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ImageViewer({ isOpen, onClose }: ImageViewerProps) {
  return (
    <Modal title="Image Viewer" isOpen={isOpen} onClose={onClose}>
      <Card title="Image Panel" className="h-full">
        <div className="flex items-center justify-center h-full min-h-[400px] text-muted-foreground">
          <div className="text-center">
            <svg
              className="w-16 h-16 mx-auto mb-4 text-muted-foreground/40"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <p className="mb-2 font-medium text-foreground">
              Image Viewer Placeholder
            </p>
            <p className="text-sm">
              View microscopy images, navigate FOVs and time points, overlay
              cell masks.
            </p>
          </div>
        </div>
      </Card>
    </Modal>
  );
}

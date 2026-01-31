import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogBody,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "../ui";

interface AnalysisWindowProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AnalysisWindow({ isOpen, onClose }: AnalysisWindowProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent fullScreen>
        <DialogHeader>
          <DialogTitle>Analysis Window</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <div className="flex gap-4 h-full">
            <Card className="flex-1">
              <CardHeader>
                <CardTitle>Data</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center h-full min-h-[300px] text-muted-foreground">
                  <div className="text-center">
                    <svg
                      className="w-12 h-12 mx-auto mb-3 text-muted-foreground/40"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    <p className="font-medium mb-1 text-foreground">Data Panel</p>
                    <p className="text-sm">Load trace data and configure fitting.</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="flex-1">
              <CardHeader>
                <CardTitle>Quality</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center h-full min-h-[300px] text-muted-foreground">
                  <div className="text-center">
                    <svg
                      className="w-12 h-12 mx-auto mb-3 text-muted-foreground/40"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <p className="font-medium mb-1 text-foreground">Quality Panel</p>
                    <p className="text-sm">Review fitting quality and metrics.</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="flex-1">
              <CardHeader>
                <CardTitle>Parameter</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center h-full min-h-[300px] text-muted-foreground">
                  <div className="text-center">
                    <svg
                      className="w-12 h-12 mx-auto mb-3 text-muted-foreground/40"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
                      />
                    </svg>
                    <p className="font-medium mb-1 text-foreground">
                      Parameter Panel
                    </p>
                    <p className="text-sm">View parameter distributions.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}

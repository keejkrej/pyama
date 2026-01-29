import { useRef } from 'react';
import { Button } from './button';

interface FilePickerProps {
  label?: string;
  accept?: string;
  multiple?: boolean;
  directory?: boolean;
  onFileSelect?: (files: FileList | null) => void;
  buttonText?: string;
  className?: string;
}

export function FilePicker({
  label,
  accept,
  multiple = false,
  directory = false,
  onFileSelect,
  buttonText = 'Browse...',
  className = ''
}: FilePickerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (onFileSelect) {
      onFileSelect(e.currentTarget.files);
    }
  };

  return (
    <div className={className}>
      {label && (
        <label className="text-xs font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 mb-1.5 block text-foreground-bright">
          {label}
        </label>
      )}
      <div className="flex items-center gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          {...(directory ? { webkitdirectory: '', directory: '' } : {})}
          onChange={handleFileChange}
          className="hidden"
        />
        <Button onClick={handleButtonClick} variant="outline">
          {buttonText}
        </Button>
      </div>
    </div>
  );
}

import { useState, useRef, type DragEvent } from "react";

interface FileDropZoneProps {
  file: File | null;
  onFileSelect: (file: File | null) => void;
}

const ACCEPTED_TYPES = [
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", // .xlsx
  "application/vnd.ms-excel", // .xls
  "text/csv",
];
const ACCEPTED_EXTENSIONS = [".xlsx", ".xls", ".csv"];

function isAcceptedFile(file: File): boolean {
  if (ACCEPTED_TYPES.includes(file.type)) return true;
  return ACCEPTED_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext));
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileDropZone({ file, onFileSelect }: FileDropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    setError(null);
    const dropped = e.dataTransfer.files[0];
    if (!dropped) return;
    if (!isAcceptedFile(dropped)) {
      setError("Please use .xlsx, .xls, or .csv files");
      return;
    }
    onFileSelect(dropped);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setError(null);
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (!isAcceptedFile(selected)) {
      setError("Please use .xlsx, .xls, or .csv files");
      return;
    }
    onFileSelect(selected);
  }

  if (file) {
    return (
      <div className="border border-rule bg-sheet px-4 py-3 flex items-center justify-between">
        <div>
          <p className="text-sm text-ink font-medium truncate">{file.name}</p>
          <p className="text-xs text-trace">{formatSize(file.size)}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            onFileSelect(null);
            if (inputRef.current) inputRef.current.value = "";
          }}
          className="text-xs text-graphite hover:text-ink transition-colors"
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border border-dashed px-4 py-6 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-ink bg-vellum"
            : "border-rule hover:border-ink/40"
        }`}
      >
        <p className="text-sm text-graphite">Drop file or click to browse</p>
        <p className="text-xs text-trace mt-1">.xlsx, .xls, or .csv</p>
      </div>
      {error && <p className="text-xs text-redline-ink mt-1">{error}</p>}
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        className="hidden"
        onChange={handleInputChange}
      />
    </div>
  );
}

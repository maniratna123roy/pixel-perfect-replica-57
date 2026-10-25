import { useEffect, useRef, useState } from "react";
import { FileVideo, UploadCloud, X } from "lucide-react";
import { isAcceptedVideoFile } from "@/config";
import { formatBytes, formatDuration } from "@/lib/demo-projects";
import type { SourceMeta } from "./view-types";

interface UploadPanelProps {
  meta: SourceMeta | null;
  hasFile: boolean;
  reselectNote?: string;
  onFileSelected: (file: File) => void;
  onDuration: (seconds: number) => void;
  onRemove: () => void;
  onGenerate: () => void;
}

export function UploadPanel({
  meta,
  hasFile,
  reselectNote,
  onFileSelected,
  onDuration,
  onRemove,
  onGenerate,
}: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasFile || !meta) {
      setPreviewUrl(null);
      return;
    }
    // Re-create the object URL whenever the File instance changes.
    return () => undefined;
  }, [hasFile, meta]);

  // Local preview: create/revoke object URLs around the current file.
  const fileRef = useRef<File | null>(null);
  useEffect(() => {
    const file = fileRef.current;
    if (!file) {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
        setPreviewUrl(null);
      }
      return;
    }
    const url = URL.createObjectURL(file);
    previewUrlRef.current = url;
    setPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
      previewUrlRef.current = null;
    };
  }, [hasFile]);

  const acceptFile = (file: File | undefined) => {
    if (!file) return;
    if (!isAcceptedVideoFile(file)) {
      setError("Unsupported file type. Please choose an MP4, MOV, or WebM video.");
      return;
    }
    setError(null);
    onFileSelected(file);
    fileRef.current = file;
  };

  const extension = meta ? (meta.name.split(".").pop()?.toUpperCase() ?? "—") : "—";

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto px-5 py-10 sm:py-16">
      <div className="w-full max-w-xl">
        <h1 className="text-3xl font-medium tracking-tight text-foreground sm:text-4xl">
          Your world, reconstructed.
        </h1>
        <p className="mt-3 text-sm text-muted-foreground sm:text-base">
          Turn aerial footage into an interactive 3D environment.
        </p>

        {reselectNote && (
          <p className="mt-4 rounded-lg border border-border bg-panel px-3.5 py-2.5 text-xs text-muted-foreground">
            {reselectNote}
          </p>
        )}

        {!hasFile || !meta ? (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              acceptFile(e.dataTransfer.files?.[0]);
            }}
            className={`mt-8 flex flex-col items-center rounded-2xl border border-dashed px-6 py-14 text-center transition-colors ${
              dragging ? "border-primary/60 bg-primary/5" : "border-border bg-panel/50"
            }`}
          >
            <UploadCloud className="h-9 w-9 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
            <p className="mt-4 text-sm font-medium text-foreground">
              Drag and drop your drone footage here
            </p>
            <p className="mt-1 text-xs text-muted-foreground">or</p>
            <button onClick={() => inputRef.current?.click()} className="btn-glass mt-3">
              Browse Files
            </button>
            <p className="mt-5 text-xs text-muted-foreground">Supported formats: MP4, MOV, WebM</p>
            {error && (
              <p className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive-foreground">
                {error}
              </p>
            )}
          </div>
        ) : (
          <div className="mt-8 overflow-hidden rounded-2xl border border-border bg-panel">
            {previewUrl && (
              <video
                src={previewUrl}
                controls
                playsInline
                onLoadedMetadata={(e) => onDuration(e.currentTarget.duration)}
                className="max-h-56 w-full bg-viewport object-contain"
                aria-label={`Preview of ${meta.name}`}
              />
            )}
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5">
              <div className="flex min-w-0 items-center gap-3">
                <FileVideo className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{meta.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {extension} &middot; {formatBytes(meta.size)}
                    {meta.duration != null && <> &middot; {formatDuration(meta.duration)}</>}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => inputRef.current?.click()} className="btn-glass px-3.5 py-1.5 text-xs">
                  Replace
                </button>
                <button
                  onClick={() => {
                    setError(null);
                    fileRef.current = null;
                    onRemove();
                  }}
                  aria-label="Remove selected file"
                  className="rounded-full border border-border p-1.5 text-muted-foreground transition-colors hover:border-destructive/50 hover:text-destructive-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            {error && (
              <p className="border-t border-border px-4 py-2.5 text-xs text-destructive-foreground">{error}</p>
            )}
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/webm"
          className="sr-only"
          aria-label="Select drone footage video"
          onChange={(e) => {
            acceptFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <button onClick={onGenerate} disabled={!hasFile} className="btn-primary-solid">
            Generate 3D Scene
          </button>
          <p className="text-xs text-muted-foreground">
            Demo mode — your file stays on this device; nothing is uploaded.
          </p>
        </div>
      </div>
    </div>
  );
}

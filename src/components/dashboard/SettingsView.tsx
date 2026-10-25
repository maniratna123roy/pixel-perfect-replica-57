import { useState } from "react";
import type { ViewerSettings, ViewPreset } from "./view-types";
import { saveViewerSettings } from "./view-types";

interface SettingsViewProps {
  settings: ViewerSettings;
  onChange: (updated: Partial<ViewerSettings>) => void;
}

export function SettingsView({ settings, onChange }: SettingsViewProps) {
  const [savedMessage, setSavedMessage] = useState(false);

  const handleUpdate = (updated: Partial<ViewerSettings>) => {
    onChange(updated);
    saveViewerSettings({ ...settings, ...updated });
    setSavedMessage(true);
    setTimeout(() => setSavedMessage(false), 2000);
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-background p-6 md:p-8">
      <div className="mx-auto w-full max-w-3xl">
        <div className="border-b border-border pb-5">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">Viewer Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Configure default camera orientation and 3D rendering viewport preferences.
          </p>
        </div>

        <div className="mt-6 space-y-6">
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="text-sm font-medium text-foreground">Default Camera View</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Starting camera angle preset when loading new 3D reconstruction scenes.
            </p>

            <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              {(["perspective", "top", "front", "side"] as ViewPreset[]).map((preset) => (
                <button
                  key={preset}
                  onClick={() => handleUpdate({ defaultView: preset })}
                  className={`rounded-lg border px-3 py-2 text-xs font-medium capitalize transition-colors ${
                    settings.defaultView === preset
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="text-sm font-medium text-foreground">Viewport Overlays</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Toggle reference indicators in the 3D viewer space.
            </p>

            <div className="mt-4 space-y-3">
              <label className="flex items-center justify-between cursor-pointer rounded-lg border border-border/60 p-3 hover:bg-muted/50">
                <div>
                  <span className="text-xs font-medium text-foreground">Ground Grid</span>
                  <p className="text-[11px] text-muted-foreground">
                    Display an orientation grid plane at origin
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={settings.showGrid}
                  onChange={(e) => handleUpdate({ showGrid: e.target.checked })}
                  className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer rounded-lg border border-border/60 p-3 hover:bg-muted/50">
                <div>
                  <span className="text-xs font-medium text-foreground">Coordinate Axes (XYZ)</span>
                  <p className="text-[11px] text-muted-foreground">
                    Display 3D Cartesian axis vectors
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={settings.showAxes}
                  onChange={(e) => handleUpdate({ showAxes: e.target.checked })}
                  className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
              </label>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="text-sm font-medium text-foreground">Reconstruction Backend & WebODM</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Photogrammetry engine used for generating dense textured 3D scenes.
            </p>

            <div className="mt-4 space-y-2.5 rounded-lg border border-border/80 bg-muted/30 p-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Backend API</span>
                <span className="font-mono text-foreground">http://localhost:8000</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">WebODM / NodeODM Node</span>
                <span className="font-mono text-foreground">http://localhost:3000</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Processing Mode</span>
                <span className="text-primary font-medium">Automatic (WebODM with Open SfM Fallback)</span>
              </div>
              <div className="mt-3 pt-3 border-t border-border/60">
                <p className="text-[11px] text-muted-foreground mb-1.5 font-medium">
                  Launch local OpenDroneMap node with Docker:
                </p>
                <code className="block rounded bg-background px-2.5 py-1.5 font-mono text-[11px] text-primary select-all">
                  docker compose -f docker-compose.webodm.yml up -d
                </code>
              </div>
            </div>
          </div>

          {savedMessage && (
            <div className="rounded-md bg-primary/10 px-3 py-2 text-xs font-medium text-primary">
              Settings updated and saved.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import {
  Component,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import {
  Environment,
  Grid,
  Html,
  Lightformer,
  OrbitControls,
  useGLTF,
  useProgress,
} from "@react-three/drei";
import * as THREE from "three";
import { clone as skeletonClone, type OrbitControls as OrbitControlsImpl } from "three-stdlib";
import {
  Axis3d,
  Camera as CameraIcon,
  Grid3x3,
  Maximize,
  Minimize,
  MousePointer2,
  Move,
  Orbit,
  RotateCcw,
  Scan,
  ZoomIn,
} from "lucide-react";
import { SAMPLE_MODEL_URL } from "@/config";
import type {
  ModelStats,
  SceneBounds,
  ViewerMode,
  ViewerSettings,
  ViewRequest,
} from "./view-types";

const MODE_LABEL: Record<ViewerMode, string> = {
  orbit: "Orbit",
  pan: "Pan",
  zoom: "Zoom",
  select: "Select",
};

interface SceneViewerProps {
  projectName: string;
  settings: ViewerSettings;
  onSettingsChange: (partial: Partial<ViewerSettings>) => void;
  onStats: (stats: ModelStats | null) => void;
  onModeChange: (mode: ViewerMode) => void;
  onSelect: (selection: string | null) => void;
}

export function SceneViewer({
  projectName,
  settings,
  onSettingsChange,
  onStats,
  onModeChange,
  onSelect,
}: SceneViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const glRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const [mode, setMode] = useState<ViewerMode>("orbit");
  const [viewRequest, setViewRequest] = useState<ViewRequest>({
    kind: settings.defaultView,
    nonce: 0,
  });
  const [bounds, setBounds] = useState<SceneBounds | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [assetFailed, setAssetFailed] = useState(false);

  const handleReady = useCallback(
    (b: SceneBounds, stats: ModelStats) => {
      setBounds(b);
      onStats(stats);
    },
    [onStats],
  );

  const handleSelect = useCallback(
    (name: string | null) => {
      onSelect(name);
    },
    [onSelect],
  );

  const setModeAndReport = useCallback(
    (next: ViewerMode) => {
      setMode(next);
      onModeChange(next);
    },
    [onModeChange],
  );

  const requestView = useCallback((kind: ViewRequest["kind"]) => {
    setViewRequest((prev) => ({ kind, nonce: prev.nonce + 1 }));
  }, []);

  useEffect(() => {
    const onFullscreenChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void containerRef.current?.requestFullscreen();
    }
  };

  const takeScreenshot = () => {
    const gl = glRef.current;
    if (!gl) return;
    const url = gl.domElement.toDataURL("image/png");
    const link = document.createElement("a");
    link.href = url;
    link.download = `${projectName.replace(/[^\w-]+/g, "-").toLowerCase() || "scene"}-view.png`;
    link.click();
  };

  const usingSample =
    assetFailed || (bounds !== null && glSampleUsed(bounds)) || SAMPLE_MODEL_URL === "";

  return (
    <div ref={containerRef} className="relative h-full w-full bg-viewport">
      <Canvas
        camera={{ fov: 55, position: [7, 5, 9] }}
        dpr={[1, 2]}
        gl={{ antialias: true, preserveDrawingBuffer: true }}
      >
        <color attach="background" args={["#0b0c0d"]} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[6, 10, 8]} intensity={1.5} />
        <directionalLight position={[-7, 4, -6]} intensity={0.5} color="#9db4c0" />
        <Environment resolution={256}>
          <Lightformer
            intensity={1.4}
            position={[0, 6, 0]}
            scale={[12, 12, 1]}
            rotation-x={Math.PI / 2}
          />
          <Lightformer
            intensity={0.6}
            color="#8ea0aa"
            position={[-6, 2, -4]}
            rotation-y={Math.PI / 2}
            scale={[16, 3, 1]}
          />
        </Environment>

        <GLGrabber glRef={glRef} />
        <OrbitControls
          ref={controlsRef}
          makeDefault
          enableDamping
          dampingFactor={0.08}
          minDistance={0.5}
          maxDistance={300}
        />
        <CameraRig request={viewRequest} bounds={bounds} controlsRef={controlsRef} />

        {SAMPLE_MODEL_URL !== "" && !assetFailed ? (
          <Suspense fallback={<LoaderOverlay />}>
            <GLTFBoundary onFallback={() => setAssetFailed(true)}>
              <SampleModel onReady={handleReady} onSelect={handleSelect} />
            </GLTFBoundary>
          </Suspense>
        ) : (
          <ProceduralSample onReady={handleReady} onSelect={handleSelect} />
        )}

        {settings.showGrid && (
          <Grid
            position={[0, 0, 0]}
            args={[40, 40]}
            cellSize={1}
            cellThickness={0.6}
            cellColor="#2e3134"
            sectionSize={5}
            sectionThickness={1}
            sectionColor="#3d4144"
            fadeDistance={60}
            fadeStrength={1.2}
            infiniteGrid
          />
        )}
        {settings.showAxes && <axesHelper args={[3]} />}
      </Canvas>

      {/* Floating overlay panels — pointer-events pass through to the canvas. */}
      <div className="pointer-events-none absolute inset-0">
        {/* Top-left: scene context */}
        <div className="glass-strong pointer-events-auto absolute left-3 top-3 rounded-xl px-3.5 py-2.5 sm:left-4 sm:top-4">
          <p className="max-w-[180px] truncate text-sm font-medium text-foreground" title={projectName}>
            {projectName}
          </p>
          <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
            Ready to explore &middot; {MODE_LABEL[mode]} mode
          </p>
        </div>

        {/* Top-right: camera + capture actions */}
        <div className="glass-strong pointer-events-auto absolute right-3 top-3 flex items-center gap-1 rounded-xl p-1 sm:right-4 sm:top-4">
          <IconButton label="Reset camera" onClick={() => requestView("reset")}>
            <RotateCcw className="h-4 w-4" />
          </IconButton>
          <IconButton label="Fit to view" onClick={() => requestView("fit")}>
            <Scan className="h-4 w-4" />
          </IconButton>
          <IconButton label="Screenshot" onClick={takeScreenshot}>
            <CameraIcon className="h-4 w-4" />
          </IconButton>
          <IconButton
            label={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
            onClick={toggleFullscreen}
          >
            {isFullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
          </IconButton>
        </div>

        {/* Left: interaction mode */}
        <div className="glass-strong pointer-events-auto absolute left-3 top-1/2 flex -translate-y-1/2 flex-col gap-1 rounded-xl p-1 sm:left-4">
          {(["orbit", "pan", "zoom", "select"] as ViewerMode[]).map((m) => (
            <IconButton
              key={m}
              label={`${MODE_LABEL[m]} mode`}
              active={mode === m}
              onClick={() => setModeAndReport(m)}
            >
              {m === "orbit" && <Orbit className="h-4 w-4" />}
              {m === "pan" && <Move className="h-4 w-4" />}
              {m === "zoom" && <ZoomIn className="h-4 w-4" />}
              {m === "select" && <MousePointer2 className="h-4 w-4" />}
            </IconButton>
          ))}
        </div>

        {/* Bottom: view presets + display toggles */}
        <div className="glass-strong pointer-events-auto absolute bottom-3 left-1/2 flex max-w-[calc(100%-1.5rem)] -translate-x-1/2 items-center gap-0.5 overflow-x-auto rounded-xl p-1 sm:bottom-4">
          {(["perspective", "top", "front", "side"] as const).map((preset) => (
            <button
              key={preset}
              onClick={() => requestView(preset)}
              aria-pressed={viewRequest.kind === preset}
              className={`whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                viewRequest.kind === preset
                  ? "bg-primary font-medium text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              {preset === "perspective" ? "Perspective" : preset[0].toUpperCase() + preset.slice(1)}
            </button>
          ))}
          <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
          <IconButton
            label={settings.showGrid ? "Hide grid" : "Show grid"}
            active={settings.showGrid}
            onClick={() => onSettingsChange({ showGrid: !settings.showGrid })}
          >
            <Grid3x3 className="h-4 w-4" />
          </IconButton>
          <IconButton
            label={settings.showAxes ? "Hide axes" : "Show axes"}
            active={settings.showAxes}
            onClick={() => onSettingsChange({ showAxes: !settings.showAxes })}
          >
            <Axis3d className="h-4 w-4" />
          </IconButton>
        </div>

        {/* Sample-scene disclosure */}
        {usingSample && (
          <p className="glass pointer-events-none absolute bottom-3 left-3 hidden rounded-lg px-3 py-2 text-[11px] text-muted-foreground sm:bottom-4 sm:left-4 lg:block">
            Sample scene — demonstration geometry, not a reconstruction of your footage.
          </p>
        )}
      </div>
    </div>
  );
}

function glSampleUsed(_bounds: SceneBounds): boolean {
  // Only used to keep the disclosure honest when the asset falls back at
  // runtime; actual fallback detection is assetFailed above.
  return false;
}

function IconButton({
  label,
  active = false,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      aria-pressed={active}
      className={`rounded-lg p-2 transition-colors ${
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function GLGrabber({ glRef }: { glRef: React.MutableRefObject<THREE.WebGLRenderer | null> }) {
  const gl = useThree((s) => s.gl);
  useEffect(() => {
    glRef.current = gl;
    return () => {
      if (glRef.current === gl) glRef.current = null;
    };
  }, [gl, glRef]);
  return null;
}

function LoaderOverlay() {
  const { progress } = useProgress();
  return (
    <Html center>
      <div className="glass-strong rounded-full px-4 py-2 text-xs text-foreground" role="status">
        {progress < 100 ? `Loading asset — ${Math.round(progress)}%` : "Preparing scene…"}
      </div>
    </Html>
  );
}

/** Renders the lit stage only; a model 404 or parse error falls back below. */
class GLTFBoundary extends Component<
  { children: ReactNode; onFallback: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.error("Failed to load reconstruction asset:", error);
    this.props.onFallback();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function useSelectionHighlight() {
  const previous = useRef<{ mesh: THREE.Mesh; emissive: THREE.Color; intensity: number } | null>(
    null,
  );
  const highlight = useCallback((mesh: THREE.Mesh | null) => {
    const prev = previous.current;
    if (prev) {
      const mat = prev.mesh.material as THREE.MeshStandardMaterial;
      if (mat && "emissive" in mat) {
        mat.emissive.copy(prev.emissive);
        mat.emissiveIntensity = prev.intensity;
      }
      previous.current = null;
    }
    if (!mesh) return;
    const mat = mesh.material as THREE.MeshStandardMaterial;
    if (mat && "emissive" in mat) {
      previous.current = {
        mesh,
        emissive: mat.emissive.clone(),
        intensity: mat.emissiveIntensity,
      };
      mat.emissive.set("#d6ff45");
      mat.emissiveIntensity = 0.25;
    }
  }, []);
  useEffect(() => () => highlight(null), [highlight]);
  return highlight;
}

function SampleModel({
  onReady,
  onSelect,
}: {
  onReady: (bounds: SceneBounds, stats: ModelStats) => void;
  onSelect: (name: string | null) => void;
}) {
  const { scene } = useGLTF(SAMPLE_MODEL_URL);
  const highlight = useSelectionHighlight();

  const object = useMemo(() => {
    const clone = skeletonClone(scene);
    const box = new THREE.Box3().setFromObject(clone);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    clone.scale.setScalar(6 / maxDim);
    const scaled = new THREE.Box3().setFromObject(clone);
    const center = scaled.getCenter(new THREE.Vector3());
    clone.position.x -= center.x;
    clone.position.z -= center.z;
    clone.position.y -= scaled.min.y;
    return clone;
  }, [scene]);

  useEffect(() => {
    const box = new THREE.Box3().setFromObject(object);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    let meshes = 0;
    let triangles = 0;
    let vertices = 0;
    object.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh && mesh.geometry) {
        meshes++;
        const g = mesh.geometry;
        const pos = g.attributes.position;
        vertices += pos ? pos.count : 0;
        triangles += g.index ? g.index.count / 3 : pos ? pos.count / 3 : 0;
      }
    });
    onReady(
      { center: [center.x, center.y, center.z], size: [size.x, size.y, size.z] },
      { format: "GLB", meshes, triangles: Math.round(triangles), vertices },
    );
  }, [object, onReady]);

  useEffect(() => () => highlight(null), [highlight]);

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    const mesh = e.object as THREE.Mesh;
    highlight(mesh);
    onSelect(mesh.name || "Unnamed mesh");
  };

  return <primitive object={object} onClick={onClick} />;
}

function ProceduralSample({
  onReady,
  onSelect,
}: {
  onReady: (bounds: SceneBounds, stats: ModelStats) => void;
  onSelect: (name: string | null) => void;
}) {
  const highlight = useSelectionHighlight();

  const geometry = useMemo(() => {
    const geo = new THREE.PlaneGeometry(14, 14, 110, 110);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    const colors = new Float32Array(pos.count * 3);
    const low = new THREE.Color("#2c2f31");
    const high = new THREE.Color("#77857b");
    const temp = new THREE.Color();
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = pos.getZ(i);
      const h =
        Math.sin(x * 0.5) * Math.cos(z * 0.42) * 0.9 +
        Math.sin(x * 1.25 + z * 0.85) * 0.32 +
        Math.sin((x + z) * 0.18) * 0.55;
      const y = (h + 1.4) * 0.85;
      pos.setY(i, y);
      const t = THREE.MathUtils.clamp((h + 1.6) / 3.2, 0, 1);
      temp.copy(low).lerp(high, t);
      colors[i * 3] = temp.r;
      colors[i * 3 + 1] = temp.g;
      colors[i * 3 + 2] = temp.b;
    }
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    return geo;
  }, []);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useEffect(() => {
    onReady(
      { center: [0, 1.3, 0], size: [14, 2.3, 14] },
      {
        format: "Sample scene",
        meshes: 1,
        triangles: 110 * 110 * 2,
        vertices: 111 * 111,
      },
    );
  }, [onReady]);

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    const mesh = e.object as THREE.Mesh;
    highlight(mesh);
    onSelect("Sample terrain");
  };

  return (
    <mesh geometry={geometry} onClick={onClick}>
      <meshStandardMaterial vertexColors roughness={0.95} metalness={0.02} />
    </mesh>
  );
}

function CameraRig({
  request,
  bounds,
  controlsRef,
}: {
  request: ViewRequest;
  bounds: SceneBounds | null;
  controlsRef: React.MutableRefObject<OrbitControlsImpl | null>;
}) {
  const goal = useRef<{ pos: THREE.Vector3; target: THREE.Vector3 } | null>(null);
  const framedOnce = useRef(false);
  const lastNonce = useRef(-1);

  const computeGoal = useCallback((kind: ViewRequest["kind"], b: SceneBounds | null) => {
    const center = b
      ? new THREE.Vector3(...b.center)
      : new THREE.Vector3(0, 1.5, 0);
    const size = b ? new THREE.Vector3(...b.size) : new THREE.Vector3(6, 3, 6);
    const d = Math.max(size.x, size.y, size.z) * 1.35 + 2;
    const pos = new THREE.Vector3();
    switch (kind) {
      case "top":
        pos.set(center.x, center.y + d, center.z + 0.01);
        break;
      case "front":
        pos.set(center.x, center.y + d * 0.12, center.z + d);
        break;
      case "side":
        pos.set(center.x + d, center.y + d * 0.12, center.z);
        break;
      default:
        pos.set(center.x + d * 0.62, center.y + d * 0.5, center.z + d * 0.72);
    }
    return { pos, target: center.clone() };
  }, []);

  // Frame the scene once when bounds first arrive.
  useEffect(() => {
    if (!bounds || framedOnce.current) return;
    framedOnce.current = true;
    goal.current = computeGoal(request.kind, bounds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bounds, computeGoal]);

  // Re-frame on explicit requests (presets, reset, fit).
  useEffect(() => {
    if (request.nonce === lastNonce.current) return;
    lastNonce.current = request.nonce;
    goal.current = computeGoal(request.kind, bounds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, computeGoal]);

  useFrame(({ camera }, delta) => {
    const g = goal.current;
    if (!g) return;
    const t = 1 - Math.exp(-6 * delta);
    camera.position.lerp(g.pos, t);
    const controls = controlsRef.current;
    if (controls) {
      controls.target.lerp(g.target, t);
      controls.update();
    }
    if (camera.position.distanceTo(g.pos) < 0.02) goal.current = null;
  });

  return null;
}

// Keep the controls in sync with the active interaction mode.
export function useViewerModeSync(
  mode: ViewerMode,
  controlsRef: React.MutableRefObject<OrbitControlsImpl | null>,
) {
  useMemo(() => undefined, []); // placeholder to keep hooks honest
  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    controls.enableRotate = mode !== "select";
    controls.mouseButtons = {
      LEFT:
        mode === "pan"
          ? THREE.MOUSE.PAN
          : mode === "zoom"
            ? THREE.MOUSE.DOLLY
            : THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    };
  }, [mode, controlsRef]);
}

useGLTF.preload?.(SAMPLE_MODEL_URL);

# Drone Video → Interactive 3D — System Architecture & Build Plan

> **Status:** Draft v1.2 — living document. New features get appended to
> [§19 Feature Backlog](#19-feature-backlog--how-to-extend) with a dated entry.
> **Owner:** MonkeyD. Luffy
> **Last updated:** 2026-10-24 (v1.2 restructures §4 into three named tracks —
> Buy, Build, Hybrid)

---

## 0. How to read this document

This is the single source of truth for building the product. It is written so
that an AI coding IDE (Cursor / Windsurf / Claude Code / Codex) can be driven
section by section:

- **§1–§3** are the *why* and the technical approach. Read once, don't edit often.
- **§4** defines the three build tracks — **Buy**, **Build**, **Hybrid** — each a
  self-contained feature with its own architecture and phase plan.
- **§5–§13** are the *what* — the architecture, contracts, stack, infra.
- **§14** is *how to build it with an AI IDE* — the workflow and rules file.
- **§15** is the *phase-wise execution plan* — this is where you spend your time.
- **§16–§20** are quality, risk, non-goals, extensibility, open questions.
- **§21** is *where the agent runs* — hosting the product on Agent37.

Every phase in §15 has a **Goal**, **Deliverables**, **Tasks**, and **Acceptance
criteria**. A phase is "done" only when its acceptance criteria pass — not when
the code compiles.

---

## 1. Vision & scope

**One-liner:** A user uploads a drone video (MP4/MOV); the system reconstructs
the captured environment and serves it back as a photorealistic, navigable,
interactive 3D scene in the browser — with the heavy compute hidden behind an
agentic orchestration layer that plans, runs, monitors, and recovers the job.

**What "interactive 3D view" means concretely:**

| Capability | Phase introduced |
|---|---|
| Free-fly / orbit / walk navigation | 1 |
| Fast load of large scenes (LOD streaming) | 4 |
| Annotations, pins, hotspots | 4 |
| Measurement (distance, height, area) | 4 |
| Auto-generated fly-through / camera paths | 4 |
| Shareable link + embed + QR | 4 |
| AR / VR (WebXR) | 5 |
| Natural-language control ("crop to the roof", "show the north face") | 5 |
| Export (glTF/OBJ/LAS/PLY, 3D-print mesh) | 3–4 |

**Explicitly in scope:** drone/UAV footage of outdoor sites, buildings,
infrastructure, terrain, construction progress, real-estate exteriors.

**Out of scope for v1:** moving-subject capture (people/animals as the subject),
fully dynamic 4D scenes, multi-drone simultaneous capture, sub-millimetre
inspection-grade metrology. (See [§18 Non-goals](#18-non-goals).)

---

## 2. Research: what Polycam is, and how it maps to this product

Polycam is the most relevant prior art because it is exactly "upload media →
cloud reconstruction → 3D output," and it exposes an API you can build on.

### 2.1 What Polycam does

- **Product:** mobile + web app that turns photos/video into 3D. Two engines:
  - **Photogrammetry** → polygonal mesh + texture maps (best for 3D printing,
    engineering, architecture, insurance documentation).
  - **Gaussian Splatting** → photorealistic radiance field (best for
    visualization, reflective/transparent/fine-detail subjects).
- **Input:** images (PNG/JPG) or video (MP4/MOV/AVI/M4V). Video is auto
  frame-extracted. Web plan limits: video **15 s minimum → 30 min max, ≤16 GB**;
  image counts per capture range from 150 (free) to 2,000 (Enterprise; 1,000 for
  splats).
- **Quality presets (photogrammetry):** Optimized / Medium / Full / Raw / Custom.
- **"Smart Keyframing":** Polycam's own algorithm auto-selects non-blurred
  keyframes from footage — this is the piece that makes *video* upload work well.
- **Processing time (their estimates):** photogrammetry ≈ 10–45 min, Gaussian
  splats ≈ 30–55 min; large photo sets run longer.

### 2.2 Polycam's APIs (the part that matters for us)

There are two APIs. **This distinction is critical — do not confuse them.**

**A) Reconstruction API** (`https://poly.cam/api/v1`) — *create* 3D models.
- Enterprise, **limited availability** — enabled per workspace by Polycam after a
  scoping call. Every token in the workspace then carries the `reconstruct` scope.
- Flow: `POST /v1/captures` (with `mode: "photo" | "splat"`, `numKeyframes`,
  optional `totalSize`) → get a signed upload URL (single PUT, or **multipart
  pre-signed parts** for multi-GB archives) → upload `session.zip` → confirm
  upload → job runs async → webhook/poll for completion.
- `session.zip` layout: `keyframes/images/*` (source photos) and, for **splat
  mode only**, a Polycam-format `frames.json` at the zip root carrying camera
  poses + intrinsics (their own format — *not* COLMAP `cameras.txt` / NeRF
  `transforms.json`). `numKeyframes` must be ≥20 and must exactly match the file
  count under `keyframes/images/`.
- **Rate limits (default):** 25 reconstruction jobs / rolling 24 h; 2 concurrent
  jobs (including jobs awaiting upload confirmation). Failed jobs still count
  against the daily limit. Exceeding either returns `429` + `Retry-After`.
- **Pricing:** prepaid credits, charged per model. Higher limits for approved
  integrations.
- **Critical implication:** the API takes *photos*, not video. **You must extract
  and select keyframes yourself** before calling it — Polycam's "Smart
  Keyframing" convenience is *not* part of the API; the app does it client-side.
  So even on the "buy" path, we own the video→keyframe stage.

**B) Content Management API** (`https://poly.cam/api/v1`) — *retrieve* captures.
- Enterprise with the `api` add-on.
- List/get captures, download artifacts, trigger export jobs, and receive
  **webhooks** (HMAC-SHA256-signed, auto-retried with backoff).
- Artifacts include `original.gltf`, `edited.gltf`, textures, `thumbnail.jpg`,
  `video.mp4` (flythrough), `original.splat` / `edited.splat` / `splat.ply`.
- Export formats: `glb`, `obj`, `fbx`, `stl`, `dae`, `usdz`, `ply`, `las`, `pts`,
  `xyz`. Non-default formats require a **Start Export Job → poll Get Export Job →
  Download Artifacts** sequence.

### 2.3 How Polycam maps to our product

| Our pipeline stage | Can Polycam do it? | Notes |
|---|---|---|
| Video ingest & storage | ❌ (we do it) | API wants a zip of images |
| Frame extraction | ❌ (we do it) | ffmpeg, our keyframe selection |
| Keyframe quality selection | ❌ (we do it) | Polycam's Smart Keyframing is app-only |
| Camera pose / SfM | ✅ (inside their engine) | opaque to us |
| Photogrammetry mesh | ✅ `mode: "photo"` | returns glTF |
| Gaussian splat | ✅ `mode: "splat"` | **requires our `frames.json`** (poses) |
| Splat/mesh post-processing, LOD | ⚠️ partial | we still run `splat-transform` |
| Hosting + interactive viewer | ❌ (we do it) | SuperSplat/Babylon/three.js |
| Job orchestration, progress, retries | ❌ (we do it) | our agent layer |

**Key insight:** Polycam removes the *GPU-hard* part (SfM + training), but it does
**not** remove the need for our own frame-extraction, pose-estimation-for-splat,
storage, orchestration, and viewer layers. It is a **reconstruction provider**,
not a product.

### 2.4 Limits that shape the design

1. **25 jobs/day, 2 concurrent** by default → a queue and backpressure are
   mandatory from day one; you cannot fire jobs straight from the API request.
2. **Splat mode needs `frames.json`** → we still need a pose-estimation step
   (COLMAP/GLOMAP) even on the buy path. This is the biggest hidden cost.
3. **Enterprise-gated + prepaid credits** → budget and access are a Phase-0
   blocker; have a self-host fallback so you are never blocked.
4. **Failure counts against quota** → validate input quality *before* submitting.

---

## 3. Core technical approaches: photogrammetry vs NeRF vs 3DGS

The three candidate scene representations:

| | Photogrammetry (mesh) | NeRF | **3D Gaussian Splatting (3DGS)** |
|---|---|---|---|
| Output | Textured polygon mesh | Implicit MLP | Millions of 3D ellipsoids |
| Photorealism | Medium | High | **High** |
| Real-time web render | Easy (small meshes) | Hard (needs per-ray NN queries) | **Yes** (rasterized) |
| Reflections / thin / transparent | Poor without prep | Good | **Good** |
| Editable / measurable geometry | **Yes** | No | Needs mesh extraction |
| File size | Small | Large | Large (compressible) |
| Streamable (LOD) | Yes | Poor | **Yes** (SOG LOD) |
| Export to CAD/BIM/print | **Yes** | No | Via mesh |

**Decision: 3D Gaussian Splatting is the primary output, with photogrammetry mesh
as a secondary deliverable.**

Rationale: the product promise is an *interactive, photorealistic* view of a
drone-captured environment. 3DGS is the only representation that is both
photorealistic and real-time in a browser, and it now has a mature web delivery
path (SOG + LOD streaming). The mesh branch matters because (a) many real
customers need measurement/export/BIM, and (b) the two branches share the entire
front half of the pipeline (ingest → frames → SfM), so adding mesh later is
cheap.

### 3.1 Drone-specific realities (this is where generic pipelines fail)

Drone footage is not phone-scan footage. The failure modes are specific:

- **Dynamic distractors** — cars, people, moving water/trees violate the
  static-scene assumption and produce artifacts/floaters. The CVPR 2025
  **DroneSplat** framework addresses exactly this (adaptive local-global masking
  + voxel-guided 3DGS + MVS geometric priors from DUSt3R for sparse views).
- **Viewpoint sparsity** — a single flight rarely covers all angles; some regions
  get 3 views. Needs MVS/DUSt3R-style geometric priors to avoid overfitting.
- **Rolling shutter + wide-angle distortion** — drop distortion parameters
  naively (the common OPENCV→PINHOLE shortcut) and you lose accuracy on
  wide-FOV drone lenses. Prefer undistortion-aware handling.
- **Motion blur / gimbal motion** — needs blur detection + keyframe selection.
- **GPS/telemetry (SRT)** — DJI `.SRT` sidecars carry GPS + gimbal attitude;
  use as a pose prior to seed or constrain SfM, and for geo-referencing.
- **Scale ambiguity** — SfM is scale-free; use GPS/known distances to metric-scale.

**These become first-class features, not afterthoughts** (see Phase 3).

---

## 4. The three build tracks — **Buy**, **Build**, **Hybrid**

One product, three interchangeable reconstruction back-ends. Everything else —
the app shell, storage, the queue, the agent (§10), the viewer (§11), Agent37
hosting (§21) — is **shared** and built once. The three tracks differ *only* in
who runs the reconstruction: a hosted API, our own GPUs, or a router over both.

All three implement the same internal interface, so they are swappable per job,
and a scene produced by any track is stored and served identically:

```
ReconstructionProvider              the one contract every track implements
  ├── PolycamProvider      →  Feature: Buy
  ├── SelfHostedProvider   →  Feature: Build
  └── RouterProvider       →  Feature: Hybrid   (chooses between the two)
```

Each track below is a **self-contained feature**: goal → architecture → its own
phase plan → acceptance criteria → when to choose → risks. Track phases carry a
prefix (`B*` Buy, `S*` Build, `H*` Hybrid) and run alongside the shared platform
phases in [§15](#15-phase-wise-build-plan).

> **Naming note.** COLMAP is an open-source SfM *engine*, not a hosted API — it
> has no first-party cloud API. The "hosted reconstruction API" track (**Buy**)
> uses **Polycam's** Reconstruction API. Any other managed reconstruction service
> slots into the same `PolycamProvider` contract, so nothing in that track is
> Polycam-specific except the wire format.

| | **Buy** | **Build** | **Hybrid** |
|---|---|---|---|
| Reconstruction runs on | Polycam cloud | our GPU workers | either, per job |
| Time to first scene | days | weeks | days (Buy) → weeks (Build) |
| Ops burden | none | CUDA + GPU scheduling | none → some |
| Per-job cost | credits / model | GPU minutes | the cheaper of the two |
| Concurrency | capped (25/day, 2 concurrent) | you set it | you set it |
| Control over quality | low | full | full |
| Vendor lock-in | high | none | none |
| Depends on | Polycam Enterprise | a GPU provider | both |

---

### 4.1 Feature — **Buy** (hosted reconstruction API)

**Goal:** ship a working end-to-end product fastest by renting the reconstruction.

**Architecture**
```
upload ─▶ our API ─▶ queue ─▶ keyframe worker (CPU) ─▶ PolycamProvider
                                                     │  create capture → upload
                                                     │  session.zip → confirm
                                                     ▼
                       webhook / poll ◀── Polycam cloud (SfM + train)
                                                     │  artifacts (gltf / splat.ply)
                                                     ▼
                       S3/R2 ─▶ splat-transform ─▶ CDN ─▶ viewer
```
We still own: ingest, frame extraction, keyframe selection, `frames.json` (poses)
for splat mode, orchestration, storage, viewer. Polycam owns SfM + training.

**Phases**

| # | Phase | Deliverable |
|---|---|---|
| B0 | Access & spike | Polycam Enterprise scoping call; one manual reconstruction through the API |
| B1 | Ingest + frames | upload, ffmpeg extraction, keyframe selection, `frames.json` writer |
| B2 | `PolycamProvider` | create → upload → confirm → webhook; retry/backoff on `429`; artifact download |
| B3 | Serve | SOG conversion, CDN, viewer page, SSE progress |
| B4 | Harden | quota/queue backpressure, failure handling, cost ledger |

**Acceptance criteria**
- Upload → interactive splat with zero manual steps.
- Splat mode works: our `frames.json` is accepted and `numKeyframes` matches files.
- A 3rd concurrent job queues instead of erroring; `429 Retry-After` respected.
- Cost per job recorded.

**When to choose:** MVP, demos, low/unknown volume, no appetite for GPU ops.
**Risks:** Enterprise gate + limited availability; 25/day & 2 concurrent;
per-model credits; opaque quality; vendor lock-in.

---

### 4.2 Feature — **Build** (self-hosted open source)

**Goal:** own the pipeline — unlimited concurrency, no per-job vendor cost, full
drone tuning.

**Architecture**
```
upload ─▶ our API ─▶ queue ─▶ GPU worker pool (autoscaled, scale-to-zero)
                              extract → select → SfM(COLMAP/GLOMAP) → mask
                              → train(gsplat/Splatfacto) → post → package
                                                     ▼
                       S3/R2 ─▶ splat-transform ─▶ CDN ─▶ viewer
```
The toolchain table in §4.4 is this track's stack; the stage contract in §6 is
how its workers are wired.

**Phases**

| # | Phase | Deliverable |
|---|---|---|
| S0 | Spike | ffmpeg → COLMAP → gsplat on one clip; timings + cost baseline |
| S1 | Stage workers | one container per stage; stage contract (§6); idempotent + resumable |
| S2 | GPU dispatch | RunPod/Modal, spawn + webhook for long jobs, scale-to-zero, max-worker cap |
| S3 | Quality | blur-aware selection, masking, GLOMAP/VGGT fallback, geo + metric scale |
| S4 | Mesh branch | dense MVS → mesh → texture → glTF |
| S5 | Optimize | caching, spot/preemptible, cost tuning, quality gates |

**Acceptance criteria**
- An unattended job with one injected failure recovers without human input.
- The same clip matches Buy-track quality within tolerance.
- Cost per job within budget; concurrency scales past the Buy cap.
- Mesh export opens in Blender/MeshLab and is measurable.

**When to choose:** scale, cost control, drone-specific quality, no vendor dependency.
**Risks:** CUDA/GPU ops, scheduling, quality tuning, GPU cost overrun.

---

### 4.3 Feature — **Hybrid** (router over both)

**Goal:** the end state — one product, two engines, chosen per job by policy.

**Architecture**
```
                      ┌──────────────────┐
 job ─▶ RouterProvider │ policy: cost,    │──▶ PolycamProvider    (Buy)
                      │ SLA, load, size, │──▶ SelfHostedProvider (Build)
                      │ customer tier    │◀── fallback on failure
                      └──────────────────┘
```
Example rules: small/low-priority → Buy; large/high-volume → Build; Buy on
`429`/failure → Build; Build GPU cold or over-budget → Buy; enterprise tier → Build.

**Phases**

| # | Phase | Deliverable |
|---|---|---|
| H0 | Interface | `ReconstructionProvider` + two impls (Buy, Build) behind it |
| H1 | Router | policy config; per-job selection; routing metrics |
| H2 | Failover | cross-provider fallback + retry ladder |
| H3 | Optimize | cost-aware routing, A/B quality, per-provider SLOs |

**Acceptance criteria**
- The same clip reconstructs on both providers with comparable artifacts.
- The router picks the cheaper provider when SLA allows, and logs the reason.
- A Buy failure transparently falls back to Build (and vice versa).
- No product code changes when a provider is added or removed.

**When to choose:** once both Buy and Build exist and volume justifies it.
**Risks:** two stacks to maintain; needs the interface locked first.

---

### 4.4 Self-hosted toolchain (the **Build** stack)

| Stage | Tool | Why |
|---|---|---|
| Frame extraction | **ffmpeg** | universal, fast |
| Keyframe selection | Python (Laplacian/CPBD blur + optical-flow spacing) | drop blur/redundant frames |
| SfM (poses + sparse cloud) | **COLMAP** (sequential matcher for video) or **GLOMAP** (global, faster, no weights) | COLMAP is the reference; GLOMAP is quicker |
| Optional feed-forward poses | **VGGT / DUSt3R / MASt3R** | when SfM fails on sparse views |
| Masking (dynamics/sky) | **SAM 2** + **GroundingDINO**, or DroneSplat heuristics | remove distractors |
| Splat training | **gsplat** (via nerfstudio **Splatfacto**) or **Inria 3DGS** or **Brush** | gsplat ≈ 4× less VRAM, ~15% faster than Inria |
| Mesh branch | COLMAP/OpenMVS dense → Poisson/Delaunay meshing → texture | secondary output |
| Splat compression + LOD | **`@playcanvas/splat-transform`** → SOG / Streamed SOG | `lod-meta.json` + chunked `.sog` |
| Viewer | **PlayCanvas SuperSplat viewer** / **Babylon.js** / **gsplat.js** / three.js | WebGL2 + WebGPU, LOD streaming |

**Hardware note:** gsplat/Splatfacto need **CUDA (NVIDIA)**. On Apple Silicon,
use **Brush** (Metal/WebGPU) — but production workers are NVIDIA GPUs. Splatfacto
needs ~6 GB VRAM, `splatfacto-big` ~12 GB; COLMAP benefits from CPU cores + RAM.

---

## 5. Target architecture

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                              CLIENT (browser / mobile web)                │
 │  Next.js app  ·  upload UI  ·  job progress (SSE/WS)  ·  3D viewer        │
 │  Viewer: SuperSplat / Babylon.js (WebGL2+WebGPU, LOD streaming, WebXR)    │
 └───────────────┬───────────────────────────────────────┬──────────────────┘
                 │ HTTPS (API)                            │ direct upload/download
                 ▼                                        │ (pre-signed URLs)
 ┌───────────────────────────────┐                        │
 │        API GATEWAY / BFF       │                        │
 │  Auth · rate-limit · routing   │                        │
 └───────────────┬───────────────┘                        │
                 ▼                                        ▼
 ┌───────────────────────────────┐              ┌───────────────────────────┐
 │   CORE BACKEND (FastAPI)       │              │   OBJECT STORAGE (S3/R2)  │
 │  Projects · Captures · Jobs    │◀────────────▶│  video/ · frames/ · poses/│
 │  Artifacts · Users · Billing   │              │  splats/ · meshes/ · thmb/│
 └───┬──────────┬──────────┬─────┘              └─────────────┬─────────────┘
     │          │          │                                  │
     │ enqueue  │ read/write│ webhooks                       │ CDN
     ▼          ▼          ▼                                  ▼
 ┌────────┐ ┌─────────┐ ┌──────────────┐            ┌───────────────────────┐
 │ Queue  │ │ Postgres│ │ ORCHESTRATION│            │  CDN (splat delivery) │
 │ Redis/ │ │ (metadata│ │    AGENT     │            │  Streamed SOG chunks  │
 │ RQ/Cel │ │  + state)│ │ planner+FSM  │            └───────────────────────┘
 └───┬────┘ └─────────┘ │ retries·QA·  │
     │                  │ cost·recover │
     │                  └──────┬───────┘
     ▼                         │ dispatch
 ┌───────────────────────────────────────────────────────┐
 │            GPU WORKER POOL (containerized, autoscaled) │
 │  Stage workers: extract → select → SfM → mask → train  │
 │  → post/LOD → package.  RunPod Serverless / Modal / k8s│
 │  (Or: PolycamProvider — external HTTP reconstruction)  │
 └───────────────────────────────────────────────────────┘
     │
     ▼
 ┌───────────────────────────────────────────────────────┐
 │  OBSERVABILITY: OpenTelemetry · Prometheus/Grafana ·   │
 │  Sentry · structured job logs · per-job cost ledger    │
 └───────────────────────────────────────────────────────┘
```

> **Deployment note:** the *orchestration agent* row below can be hosted on
> **Agent37** (one isolated sandbox per customer) instead of self-managed — see
> [§21](#21-building--hosting-on-agent37). The GPU worker pool stays external:
> Agent37 sandboxes are CPU-only and have no GPUs.

### 5.1 Component responsibilities

| Component | Responsibility | Notes |
|---|---|---|
| **Client app** | Upload, progress, viewer, sharing, account | Next.js; uploads go **direct to object storage** via pre-signed URLs (never through the API) |
| **API gateway / BFF** | Auth, rate limiting, request routing | Thin; JWT; per-user quotas |
| **Core backend** | Domain logic: projects, captures, jobs, artifacts, billing | FastAPI + SQLAlchemy; stateless, horizontally scalable |
| **Queue** | Decouple API from GPU work; backpressure; retries | Redis + RQ/Celery (start) → Temporal (scale) |
| **Postgres** | Source of truth for metadata + job state machine | Jobs table is the coordination point |
| **Object storage** | Videos, frames, poses, splats, meshes, thumbnails | S3/R2/GCS; lifecycle rules; pre-signed access |
| **CDN** | Serve large splat/SOG chunks fast and cheap | Streamed SOG is chunked → cacheable |
| **Orchestration agent** | Plan → dispatch → monitor → validate → recover → report | See §10 |
| **GPU worker pool** | Run pipeline stages | One image per stage; scale to zero |
| **Reconstruction provider** | SfM + train (+mesh) | `PolycamProvider` \| `SelfHostedProvider` |
| **Observability** | Traces, metrics, logs, cost | Every job emits a span tree + cost ledger row |

### 5.2 Why these boundaries

- **Direct-to-storage uploads** — a 16 GB video must not pass through the API
  process; pre-signed multipart PUT scales and is what Polycam does too.
- **Queue between API and GPU** — GPU jobs take 10–60 min; HTTP requests cannot.
  The API returns `202 + job_id` immediately.
- **Provider interface** — makes build/buy reversible (§4).
- **CDN + chunked SOG** — a 200 MB splat must stream progressively, not block.

---

## 6. The reconstruction pipeline in detail

Each stage is an idempotent, independently re-runnable worker that reads/writes
object storage and records its status in Postgres. **Idempotency + skip-if-outputs-
exist is mandatory** — it is what makes retries and partial re-runs cheap.

```
S0  INGEST        validate container/codec/duration/size; probe with ffprobe;
                  pull SRT/GPS sidecar; create Capture + Job rows
S1  EXTRACT       ffmpeg → frames at target fps (2–5 fps typical; subsample from
                  30 fps); preserve EXIF/telemetry; 360 → cubemap if equirect
S2  SELECT        blur score (Laplacian variance / CPBD) + optical-flow spacing →
                  keep N sharp, well-spaced keyframes (target ~150–400)
S3  POSES         COLMAP sequential_matcher → mapper  |  GLOMAP  |  VGGT/DUSt3R
                  → cameras + sparse points; normalize camera model; geo-register
                  with GPS/SRT if available
S4  MASK (opt)    SAM2/GroundingDINO or DroneSplat heuristics → drop dynamic
                  distractors & sky; write per-frame masks
S5  RECONSTRUCT   ├─ SPLAT: gsplat/Splatfacto/Inria/Brush → splat .ply (+ eval:
                  │         PSNR/SSIM/LPIPS on held-out views)
                  └─ MESH:  dense MVS → meshing → texture → glTF/GLB
                  (Polycam path: this stage = external API call)
S6  POST          splat cleanup (cull floaters, crop), decimate mesh, orient/scale,
                  generate thumbnail + fly-through MP4
S7  PACKAGE       splat-transform → SOG (single) or Streamed SOG (LOD bundle,
                  `lod-meta.json` + chunks) when ≥1M gaussians; mesh → glb/usdz
S8  PUBLISH       write artifacts + manifest to storage; invalidate CDN; emit
                  webhook; mark Job complete
```

**Per-stage contract (uniform):**

```jsonc
// worker input
{ "job_id": "...", "stage": "S3_POSES",
  "inputs":  { "frames_prefix": "s3://.../frames/<job>/" },
  "outputs_prefix": "s3://.../poses/<job>/",
  "params": { "matcher": "sequential", "overlap": 30 } }
// worker output
{ "status": "ok|failed|skipped",
  "outputs": { "sparse_model": "s3://.../poses/<job>/0" },
  "metrics": { "registered_images": 187, "duration_s": 402 },
  "warnings": [] }
```

**Quality gates (the agent's feedback signal):**
- S2: ≥ 60% of extracted frames survive selection; else warn "poor footage".
- S3: ≥ 80% of keyframes registered in the largest sub-model; else try GLOMAP/VGGT.
- S5: held-out PSNR/SSIM above threshold; else flag for re-train or re-select.
- S6: splat size within budget; floater heuristic pass.

---

## 7. Data model (Postgres, first cut)

```
users(id, email, name, created_at, tier)
projects(id, user_id, name, description, created_at, visibility)
captures(id, project_id, source_type, storage_key, bytes, duration_s, fps,
         resolution, has_gps, srt_key, created_at)
jobs(id, capture_id, status, provider, pipeline_version, params_json,
     priority, cost_estimate, cost_actual, started_at, finished_at, error)
job_stages(id, job_id, stage, status, attempt, inputs_json, outputs_json,
           metrics_json, warnings_json, started_at, finished_at)
artifacts(id, job_id, kind, format, storage_key, bytes, meta_json)  -- splat|mesh|thumb|video|las
scenes(id, capture_id, primary_artifact_id, lod_manifest_key, bbox,
       scale_meters, geo_origin, camera_path_key, created_at)
annotations(id, scene_id, kind, position, payload_json, author_id, created_at)
shares(id, scene_id, token, expires_at, allow_download)
events(id, job_id, type, payload_json, created_at)   -- audit + webhook source
```

`jobs.status` state machine:

```
created → queued → running → (succeeded | failed | cancelled)
                       ↑           │
                       └── retrying ┘   (per-stage retries; agent may re-plan)
```

---

## 8. API contracts (v1, illustrative)

```
POST   /v1/captures/init        → { capture_id, upload: {url | multipart parts} }
POST   /v1/captures/{id}/commit → validates upload, enqueues job → { job_id }
POST   /v1/jobs                 → { capture_id, options } → { job_id }        (202)
GET    /v1/jobs/{id}            → { status, progress, current_stage, stages[], error }
GET    /v1/jobs/{id}/events     → SSE stream of stage transitions
GET    /v1/scenes/{id}          → { lod_manifest_url, bbox, camera_path, annotations }
POST   /v1/scenes/{id}/annotations
POST   /v1/scenes/{id}/share    → { token, url }
POST   /v1/scenes/{id}/export   → { format } → export job → artifact
POST   /v1/agent/chat           → { scene_id, message } → agent actions (Phase 5)
GET    /healthz  /metrics  /version
```

**Webhooks out:** `job.completed`, `job.failed`, `scene.published` (HMAC-signed,
retried with backoff — mirror Polycam's design).

**Progress delivery:** SSE preferred over polling for stage-level progress;
fall back to polling for restrictive networks.

---

## 9. Tech stack

| Layer | Choice | Alternative |
|---|---|---|
| Frontend | Next.js + TypeScript + Tailwind | Remix, SvelteKit |
| 3D viewer | Babylon.js **or** PlayCanvas SuperSplat viewer | gsplat.js, three.js + mkkellogg loader |
| Backend | FastAPI (Python) + SQLAlchemy + Pydantic | Django (better admin), NestJS |
| Queue | Redis + RQ/Celery | Temporal (durable, better at scale) |
| DB | Postgres | — |
| Object storage | S3 / Cloudflare R2 | GCS, Azure Blob |
| CDN | Cloudflare | CloudFront |
| GPU | RunPod Serverless / Modal | k8s + GPU node pool, AWS Deadline Cloud |
| Pipeline | ffmpeg, COLMAP/GLOMAP, gsplat/Splatfacto, Brush, splat-transform | Inria 3DGS, OpenSplat, LichtFeld |
| Splat delivery | SOG / Streamed SOG (`lod-meta.json`) | SPZ, compressed PLY |
| Observability | OpenTelemetry + Grafana + Sentry | Datadog |
| IaC | Terraform + Docker | Pulumi |

**Python for the pipeline is deliberate** — the entire open-source 3DGS ecosystem
(gsplat, nerfstudio, COLMAP bindings, SAM2, DUSt3R) is Python-first. Keep the
backend in Python too so workers and API share types and helpers.

---

## 10. The agentic orchestration layer

The user calls this an "AI agent," so the orchestration must be genuinely agentic,
not just a cron pipeline. But it must also be **deterministic where it counts**.

**Design: a planner + deterministic FSM + a validation loop.**

```
        ┌─────────────┐   plan    ┌──────────────┐  dispatch  ┌────────────┐
upload →│  PLANNER    │──────────▶│  EXECUTOR    │───────────▶│ GPU WORKER │
        │ (LLM +      │           │ (deterministic│◀───────────│  stages    │
        │  rules)     │◀──────────│  FSM + queue) │  metrics   └────────────┘
        └─────────────┘  feedback └──────────────┘
              │                          │
              ▼                          ▼
        ┌─────────────┐           ┌──────────────┐
        │  VALIDATOR  │           │  RECOVERY    │
        │ quality     │──────────▶│ retry / re-   │
        │ gates (§6)  │  fail     │ plan / fallback│
        └─────────────┘           └──────────────┘
```

- **PLANNER** — LLM-backed, *bounded*. Given capture metadata (duration,
  resolution, fps, has_gps, estimated scene size) it picks: provider (Polycam vs
  self-host), fps/selection target, matcher, trainer, masking on/off, quality
  tier. It outputs a **typed plan JSON**, never free-form actions. Deterministic
  rules cover 90% of cases; the LLM handles the long tail and natural-language
  user requests.
- **EXECUTOR** — a deterministic state machine that walks §6's stages, writes
  `job_stages` rows, and is fully replayable. The LLM never directly runs a shell
  command.
- **VALIDATOR** — applies the quality gates from §6. On failure, emits a
  structured signal.
- **RECOVERY** — policy ladder: retry stage → change params (e.g. COLMAP→GLOMAP)
  → switch provider (self-host→Polycam) → ask the user. Bounded attempts.

**Why this split:** LLMs are good at *choosing among known strategies* and
*explaining failures*; they are bad at reliably orchestrating long GPU jobs.
Keep the FSM deterministic and let the LLM own the decision points. This also
makes the whole thing testable (mock the planner, assert the FSM).

**Phase 5 adds the conversational surface:** `POST /v1/agent/chat` where a user
says "reconstruct just the roof, at high detail" and the planner emits a new
scoped job. Ground this on the scene's artifacts (bbox, camera path), never on
hallucinated geometry.

---

## 11. Viewer & interactive layer

**Requirements:** open a 200 MB–2 GB splat on a phone and a desktop, stream it
progressively, stay at a good frame rate, and let the user *do* things.

- **Renderer:** WebGL2 with WebGPU when available (both PlayCanvas and Babylon
  support this and auto-fall-back).
- **Streaming:** generate **Streamed SOG** with `splat-transform`:
  ```
  splat-transform input.ply -C 512 -X 16 output/lod-meta.json
  ```
  → `lod-meta.json` + chunked `.sog`. The viewer loads the coarsest LOD first
  (near-instant first frame, no holes) and streams finer LODs by camera distance
  against a **splat budget** (e.g. desktop 4M, mobile 1M gaussians).
- **Interaction layer (our own, on top of the renderer):**
  - Annotations/pins anchored in 3D (persist in Postgres, keyed to scene bbox).
  - Measurement — needs a mesh/collision proxy; the mesh branch (S5b) supplies it.
  - Camera-path authoring + auto fly-through (S6 already renders one).
  - Share links + iframe embed + QR.
  - WebXR (AR/VR) — force the WebGL renderer path.
- **Fallback:** for very large scenes or low-end devices, offer the mesh + a
  simpler three.js view, or a pre-rendered fly-through video.

---

## 12. Infrastructure, GPU & cost

**GPU is the cost centre.** Reference points (approximate, verify before quoting):

- Serverless GPU (RunPod RTX 4090 class) ≈ $0.44–0.69/hr; Modal A10G ≈ $1.10/hr,
  A100 ≈ $3.73/hr; RunPod has no region/preemption multipliers, Modal's
  guaranteed-non-preemptible tier is ~3× base.
- A typical drone job: frame extract (CPU, minutes) + SfM (CPU/GPU, 10–30 min) +
  splat train (GPU, 20–60 min). **Budget $1–5 of GPU per job** at MVP scale.
- **Long jobs break naive serverless HTTP**: Modal web endpoints hard-timeout at
  150 s, so use the spawn pattern (return immediately, run in background, webhook
  on completion). This is exactly why our API is async-first.
- **Polycam path** removes GPU cost but adds per-model credits + the 25/day cap.

**Scaling strategy:**
1. API + Postgres + queue scale horizontally (stateless).
2. GPU workers **scale to zero**, one stage = one container; cap max workers.
3. Priority lanes (paid tier jumps the queue).
4. Cache aggressively: content-hash inputs → reuse prior outputs on identical
   re-uploads.

**Cost controls:** per-job cost ledger (already in the data model), budget alarms,
per-user quotas, provider router that prefers the cheaper option when SLA allows.

---

## 13. Security, privacy & compliance

- **Uploads** via short-lived pre-signed URLs; no standing credentials in clients.
- **Secrets** in a managed secret store; never in code or images (see §14 rules).
- **API tokens** hashed at rest, scoped, revocable, expiring (mirror Polycam).
- **Data retention** policy per tier; delete video after N days, keep splat;
  user-triggered hard delete.
- **Geo-privacy:** drone footage may capture private property/people. Offer a
  "blur faces/plates" option (SAM2 + detector) before publishing, and store GPS
  at reduced precision by default.
- **Access control:** scene-level ACLs; share tokens are scoped + expiring.
- **Compliance:** SOC 2-style controls if selling to enterprise; note that if you
  route through Polycam, *their* SOC 2 Type I & II covers their side only.
- **Abuse:** rate limits, size limits, and a review path for public shares.

---

## 14. Building this with an AI IDE

The plan is designed to be executed by an AI coding IDE. Rules that make that work:

**14.1 Create a rules/context file** at repo root — `AGENTS.md` (also symlinked or
duplicated as `.cursor/rules`, `.windsurfrules`, `CLAUDE.md` as needed). It must
state, in this order:
1. The product one-liner and the §5 architecture diagram.
2. **The stage contract (§6)** and the `ReconstructionProvider` interface (§4) —
   the AI must not change these without an explicit task.
3. The stack (§9) and the "no new dependency without a task" rule.
4. The secrets rule: **never hardcode credentials; read from env / secret store;
   use placeholders in examples.**
5. The testing rule: every worker stage has a **mock mode** (tiny synthetic input)
   so the pipeline runs end-to-end on CPU with no GPU.
6. The idempotency rule: stages skip if outputs exist unless `overwrite: true`.

**14.2 Work in vertical slices, one phase task at a time.** Each §15 task is sized
for one AI session: give the IDE the task text + the relevant §6 contract + the
acceptance criteria, ask for the code *and* its test, review, then move on.

**14.3 Build the mock pipeline first.** A `--mock` mode that fakes SfM and
training with a canned splat lets you build the *entire* product (upload → queue →
progress → viewer) on a laptop with no GPU. Swap in real workers in Phase 2.

**14.4 Keep contracts in code, not prose.** Define the stage input/output and
provider interface as typed Pydantic models / TS types. The IDE and the workers
then share one source of truth, and drift is caught by the type checker.

**14.5 Prompt pattern per task** (paste into the IDE):
> "Implement <task>. Respect AGENTS.md. Follow the stage contract in
> `contracts/stages.py` and the provider interface in
> `providers/base.py`. Add tests using the mock fixtures in `tests/fixtures/`.
> Do not add dependencies. Output the diff and the test run."

**14.6 Definition of done for every AI-generated change:** types pass, tests pass,
mock pipeline still runs end-to-end, no secrets, contract unchanged (or the change
was the explicit task).

---

## 15. Phase-wise build plan (shared platform)

> These phases build the **shared platform** — app shell, storage, queue, agent,
> viewer, scale. They are common to all three tracks in [§4](#4-the-three-build-tracks--buy-build-hybrid).
> The reconstruction back-end is whichever track you picked; that track's own
> phases (`B*` Buy, `S*` Build, `H*` Hybrid) run alongside these.

Each phase below: **Goal → Deliverables → Tasks → Acceptance criteria.**
Phases are cumulative; later phases assume earlier contracts.

---

### Phase 0 — Foundations & spike (≈ 1 week)

**Goal:** De-risk the two unknowns (does the pipeline work on *our* footage; can we
get Polycam access) and lock the contracts before writing product code.

**Deliverables**
- A 5–10 min DJI-style test video + a second, harder one (dynamic traffic).
- A **throwaway spike**: ffmpeg → COLMAP → gsplat (or Brush) → `.ply`, run once,
  on a rented GPU. Success = a splat you can open in SuperSplat.
- Polycam Enterprise demo booked; API access scoping call done (or a documented
  fallback plan).
- `AGENTS.md` + repo skeleton + the stage contract and provider interface stubs.

**Tasks**
1. Collect 3–5 representative drone clips (varied: building, terrain, dynamic).
2. Run the spike end-to-end; record times, GPU used, and failure modes.
3. Decide fps/keyframe targets and initial quality gates from the spike.
4. Write `AGENTS.md` and commit the architecture diagram.
5. Define `contracts/stages.py` and `providers/base.py`.

**Acceptance criteria**
- A `.ply` splat from real drone footage opens in a browser viewer.
- Spike timings give a first GPU-cost estimate per job.
- Contracts are typed, committed, and referenced by `AGENTS.md`.

---

### Phase 1 — MVP happy path (≈ 2–3 weeks)

**Goal:** A user can upload a video and see an interactive 3D scene, end to end,
using the **Polycam provider** (or the spike pipeline wrapped as a worker).

**Deliverables**
- Next.js app: auth, project, upload (pre-signed direct), job page with progress.
- FastAPI backend + Postgres + Redis queue + object storage.
- `PolycamProvider` implemented (create capture → upload session.zip → confirm →
  webhook/poll → download artifacts). **Includes our own frame extraction +
  `frames.json` generation** for splat mode.
- Minimal viewer page that loads the resulting splat.
- Mock pipeline so devs without GPU/API access can run the full flow.

**Tasks**
1. Storage + pre-signed upload (single + multipart).
2. Domain models (§7) + migrations.
3. Queue + worker skeleton + `job_stages` tracking.
4. Frame extraction (S1) + basic selection (S2) + `frames.json` writer (S3-lite).
5. `PolycamProvider` with retry/backoff honouring `429 Retry-After`.
6. Viewer page (SuperSplat/Babylon) + thumbnail.
7. SSE progress.

**Acceptance criteria**
- Upload → processing → interactive splat in the browser, no manual steps.
- Job survives a worker restart (resumable from `job_stages`).
- Rate-limit handling: a 3rd concurrent job queues rather than erroring.
- Mock mode runs the whole flow on a CPU-only laptop.

---

### Phase 2 — Own the pipeline (self-hosted GPU) (≈ 3–4 weeks)

**Goal:** Add `SelfHostedProvider` and a provider router so we are not gated by
Polycam availability or quotas.

**Deliverables**
- Containerized stage workers: extract, select, SfM (COLMAP + GLOMAP), train
  (gsplat/Splatfacto), post, package.
- GPU worker deployment on RunPod Serverless / Modal with the **spawn + webhook**
  pattern for long jobs.
- `ProviderRouter` (cost/SLA/load/size policy).
- Splat → SOG conversion (`splat-transform`).
- Per-job cost ledger.

**Tasks**
1. One Docker image per stage; stage contract respected.
2. GPU dispatch with autoscaling to zero + max-worker cap.
3. GLOMAP fallback when COLMAP under-registers.
4. Quality metrics (PSNR/SSIM/LPIPS) captured into `metrics_json`.
5. Router + config; A/B Polycam vs self-host on the same clips.

**Acceptance criteria**
- Same clip reconstructs on both providers; artifacts are comparable.
- A job runs unattended with 0 manual intervention, incl. one injected failure.
- Cost per job recorded and within budget target.
- Router demonstrably picks the cheaper provider when SLA allows.

---

### Phase 3 — Quality & drone robustness (≈ 3–4 weeks)

**Goal:** Make reconstruction *reliable on real drone footage*, which is the hard
part.

**Deliverables**
- Blur-aware keyframe selection; GPS/SRT ingestion as pose prior + metric scale.
- Dynamic-distractor masking (SAM2/GroundingDINO or DroneSplat-style heuristics).
- Sparse-view handling (DUSt3R/VGGT priors) when registration is weak.
- Wide-angle/rolling-shutter handling (undistortion-aware, not naive drop).
- **Mesh branch** (dense MVS → mesh → texture → glTF) for measurement/export.
- Auto-retry ladder wired to the validator.

**Tasks**
1. SRT parser → GPS/attitude → geo-registration + scale.
2. Blur scoring + adaptive selection target.
3. Masking pipeline + per-frame masks; verify floater reduction.
4. Feed-forward pose fallback (VGGT/DUSt3R).
5. Mesh branch + texture; validate in an independent viewer.
6. Quality-gate thresholds tuned from a labelled set of clips.

**Acceptance criteria**
- Dynamic scene reconstructs without vehicle/person ghosts above threshold.
- Metric scale within a stated tolerance on a GPS-tagged clip.
- Weak-registration clip recovers via the fallback instead of failing.
- Mesh export opens in Blender/MeshLab and is measurable.

---

### Phase 4 — Viewer & interactivity (≈ 3 weeks)

**Goal:** The "interactive" promise, fully realized.

**Deliverables**
- Streamed SOG LOD delivery + CDN; instant first frame.
- Annotations/pins, measurement, camera-path authoring, auto fly-through.
- Share links, iframe embed, QR; scene ACLs.
- Exports (glTF/OBJ/USDZ/LAS/PLY).

**Tasks**
1. `splat-transform` LOD bundle + `lod-meta.json` serving via CDN.
2. Splat budget + device-aware quality presets.
3. Annotation CRUD anchored to scene coordinates.
4. Measurement tool (mesh collision proxy).
5. Camera path + video render.
6. Sharing/embed + expiring tokens.

**Acceptance criteria**
- 500 MB+ scene reaches first frame < 3 s on desktop, < 6 s on mobile.
- Sustained frame rate above target with the splat budget enforced.
- Annotations survive reload and are correct after camera moves.
- Measurement matches a known distance within tolerance.

---

### Phase 5 — Agentic layer & natural-language control (≈ 3–4 weeks)

**Goal:** Turn the orchestration into a true agent and expose it to users.

**Deliverables**
- Planner (LLM + rules) emitting typed plan JSON; validator + recovery ladder.
- `POST /v1/agent/chat` — natural-language scoping ("roof only, high detail"),
  re-planning, and failure explanation in plain language.
- Failure auto-recovery: retry → re-param → provider switch → ask user.
- Cost/quality-aware planning.

**Tasks**
1. Typed plan schema + deterministic rules + LLM tail.
2. Validator signals → recovery policy ladder (bounded attempts).
3. Chat endpoint grounded on scene artifacts (bbox, camera path) only.
4. Guardrails: LLM never emits shell/commands; all actions are typed.
5. Explanations for failures (why a job failed, what to change in the footage).

**Acceptance criteria**
- Given a scoped NL request, the system produces a correct typed plan and runs it.
- An injected mid-pipeline failure is recovered without human input.
- No path exists where the LLM executes arbitrary commands.

---

### Phase 6 — Scale, multi-tenancy & compliance (≈ 3–4 weeks)

**Goal:** Production hardening.

**Deliverables**
- Multi-tenant orgs, roles, quotas, billing hooks.
- Retention policies, hard delete, face/plate blur option, GPS precision control.
- Observability dashboards + SLOs + on-call runbooks.
- Terraform IaC; blue/green worker deploys.

**Tasks**
1. Orgs/roles/quotas + per-tenant isolation.
2. Retention jobs + GDPR-style delete.
3. Privacy blur pre-publish.
4. Dashboards: queue depth, GPU hours, failure rate, p95 latency, cost/job.
5. Load test: N concurrent uploads → queue → completion without degradation.

**Acceptance criteria**
- Isolation verified (no cross-tenant data access).
- SLOs met under load test; alarms fire on breach.
- Hard delete removes all artifacts, verifiably.

---

### Phase 7 — Extensibility & new features (ongoing)

**Goal:** Make adding features cheap — this is where the user's future requests land.

**Deliverables**
- Plugin-style stage registry (add a stage without touching the FSM core).
- Feature flags + a documented extension recipe.
- Versioned `pipeline_version` so old scenes remain viewable.

**Extension recipe (use this for every new feature request):**
1. Append a dated entry to [§19](#19-feature-backlog--how-to-extend).
2. Classify: new *stage* (fits the stage contract) / new *provider* / new *viewer
   capability* / new *agent action* / new *infra*.
3. Write the acceptance criteria before the code.
4. If it's a stage, register it; if it's a viewer feature, it's client-only and
   ships without touching the pipeline.
5. Update `pipeline_version` if it changes outputs.

**Acceptance criteria:** the feature is demonstrable on an existing scene, with
tests, and does not regress §16.

---

## 16. Testing & quality strategy

- **Mock pipeline (CPU-only):** every stage has a mock; the whole flow runs in CI
  with no GPU and no Polycam account. This is the backbone of fast iteration.
- **Contract tests:** stage input/output and provider interface are typed; any
  drift fails CI.
- **Golden scenes:** a small fixed set of clips with expected quality ranges
  (PSNR/SSIM/LPIPS bands, registered-image %, splat size). Regression = out of band.
- **Idempotency tests:** re-running any stage with outputs present is a no-op.
- **Failure injection:** kill workers mid-stage, expire tokens, simulate `429`s,
  corrupt an upload — assert recovery.
- **Viewer tests:** headless screenshot comparison across devices (Playwright).
- **Load tests:** queue + GPU pool under concurrent uploads.

---

## 17. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Polycam access not granted / quota too low | Blocks buy path | Self-hosted provider (Phase 2); frame the buy path as optional |
| GPU cost overrun | Margin | Cost ledger, quotas, provider router, scale-to-zero, caching |
| Poor drone footage (blur, low overlap) | Bad scenes, wasted GPU | Pre-flight validation + quality gates + "improve your capture" guidance |
| Dynamic distractors | Ghosts/floaters | Masking + DroneSplat-style handling (Phase 3) |
| Large splats slow on mobile | Bad UX | Streamed SOG + splat budget + quality presets |
| Splat file formats churn (SPZ/SOG/KSPLAT) | Rework | Always keep source `.ply`; treat delivery formats as swappable |
| Long serverless jobs time out | Silent failures | Async API + spawn/webhook pattern + durable queue |
| CUDA/toolchain drift | Broken builds | Pinned images, per-stage containers, CI build check |
| Legal/privacy (property, faces) | Compliance | Blur options, retention, ACLs |

---

## 18. Non-goals

- Sub-millimetre / metrology-grade accuracy.
- Real-time (live) reconstruction from a drone video stream (v1 is batch).
- Fully dynamic 4D scenes (moving objects reconstructed as moving).
- Indoor phone-scan parity (LiDAR/ARKit workflows).
- Being a general CAD/BIM authoring tool (we export; we don't model).
- Training our own foundation reconstruction model.

---

## 19. Feature Backlog & how to extend

> **This is the section the user edits when adding features.** Newest first.
> Each entry: `### YYYY-MM-DD — <feature>` with Goal / Class / Acceptance criteria.

### 2026-10-24 — Initial plan
- Goal: baseline architecture + phased build plan (this document).
- Class: foundation.
- Acceptance: the doc is agreed and Phase 0 can start.

### 2026-10-24 — Agent37 as the agent-hosting plane
- Goal: host the orchestration agent and per-customer sandboxes on Agent37;
  keep GPU reconstruction external. Details in [§21](#21-building--hosting-on-agent37).
- Class: infra / hosting.
- Acceptance: one Agent37 instance runs the harness, `exec`s ffmpeg, calls the
  external GPU provider, and streams chat to the app via `/v1/responses`.

### 2026-10-24 — Three build tracks: Buy / Build / Hybrid
- Goal: expose reconstruction as three interchangeable features behind one
  `ReconstructionProvider` contract. Details in [§4](#4-the-three-build-tracks--buy-build-hybrid).
- Class: core architecture.
- Acceptance: all three tracks implement the interface; a scene from any track is
  served identically; switching tracks needs no product-code change.

*(Future feature requests get appended here before implementation, per the Phase 7
recipe.)*

---

## 20. Open questions / decisions to confirm

1. **Provider strategy:** commit to Path C (hybrid) now, or ship Path A only and
   defer self-hosting? *(Recommend hybrid interface from day one, implementation
   staggered.)*
2. **Primary output:** splat-first (recommended) or mesh-first? Affects Phase 3
   ordering.
3. **Target device floor:** must it run on mid-range Android? Sets the splat
   budget and whether a mesh/video fallback is required.
4. **Deployment region / data residency:** India-first hosting? Affects storage
   and CDN choice.
5. **Pricing model:** per-scene credits vs subscription? Affects the quota system.
6. **Polycam:** is an Enterprise contract acceptable, or is it out entirely?

---

## 21. Building & hosting on Agent37

> **What Agent37 is:** a cloud sandbox platform for hosting AI agent harnesses
> (Hermes, OpenClaw, Claude Code, Codex, OpenCode, Grok, Pi) or your own Docker
> image. Each agent gets an isolated, persistent Linux sandbox — or a full VM —
> reachable over HTTPS, with a chat API, file/exec access, scheduled runs,
> managed LLM access, and 1,000+ app integrations. Billing is per minute; an idle
> sandbox costs only its disk. (Y Combinator, Fall 2026.)

### 21.1 The one thing to get right: Agent37 is not a GPU

Agent37 instances are **CPU sandboxes** (default 2 vCPU / 4 GB, up to 4 vCPU /
16 GB). There is **no GPU**. So Agent37 **cannot** run COLMAP SfM or gsplat
training — the expensive half of the pipeline in §6. Split the system by plane:

| Plane | Where it runs | What it does |
|---|---|---|
| **Agent plane** | **Agent37** | conversational agent, planning (§10), job state, files, exec, scheduling, integrations, per-customer isolation |
| **GPU plane** | RunPod / Modal / Polycam (external) | frame SfM, splat/mesh reconstruction |
| **Storage plane** | S3 / R2 + CDN | video, frames, splats, SOG chunks |
| **Frontend** | Vercel/Cloudflare, or an `agent37-ubuntu` VM port | upload UI + 3D viewer |

Agent37 sandboxes have **public-internet egress only** — exactly what you need:
the agent calls the GPU provider's API and the Polycam API as ordinary tools.
Keep large media in object storage, not in the sandbox — sandbox disks are
4–40 GB and the container-image cap is 8 GB, so a CUDA/COLMAP image would not fit
anyway. That is a *second* reason the GPU stays off Agent37.

```
 ┌──────────────────────── AGENT37 (per customer) ────────────────────────┐
 │  instance (gVisor sandbox, CPU)   https://{instanceId}.agent37.app      │
 │   ├─ agent harness (Hermes / your custom image)                        │
 │   ├─ Agent API: POST /v1/responses  (chat, SSE streaming)              │
 │   ├─ files · exec · web terminal · live desktop                        │
 │   ├─ scheduled runs (cron) · skills / plugins                          │
 │   ├─ managed LLM (AGENT37_LLM_PROXY_URL) · Composio (Gmail/Slack/Drive)│
 │   └─ tools → call out over public internet:                            │
 └───────────┬──────────────────────────┬─────────────────────────────────┘
             │ HTTPS                     │ HTTPS
             ▼                           ▼
   ┌────────────────────┐     ┌──────────────────────┐
   │ GPU plane          │     │ Polycam API          │
   │ RunPod / Modal     │     │ (optional provider)  │
   │ COLMAP + gsplat    │     └──────────────────────┘
   └─────────┬──────────┘
             │ artifacts
             ▼
   ┌──────────────────────────────────────────┐
   │ S3 / R2  +  CDN  →  browser 3D viewer     │
   └──────────────────────────────────────────┘
```

### 21.2 The two API planes (one key)

Mint an `sk_live_...` key. Two base URLs, two headers:

| Plane | Base URL | Header | Use |
|---|---|---|---|
| Sandbox API | `https://api.agent37.com/v1` | `Authorization: Bearer sk_live_...` | create/manage instances, templates, budgets |
| Agent API | `https://{instanceId}.agent37.app` | `X-Agent37-Key: sk_live_...` | `POST /v1/responses` chat, `/v1/sessions`, `/v1/files`, `/v1/models`, `/v1/health` |

The instance id doubles as the hostname. Any other port is reachable at
`https://{instanceId}-{port}.agent37.app` — so a backend or viewer on `:8000` is
at `https://{instanceId}-8000.agent37.app`, with no port registration.

### 21.3 How the product maps onto Agent37

1. **One instance per customer** (Agent37's own model). Create at signup:
   `POST /v1/instances` with
   `{ "user": "u_123", "name": "scene-u_123", "budget": { "credit_micros": 1000000 }, "auto_sleep": true }`,
   then store `inst.id` on the user row.
2. **Chat is the product's brain.** `POST https://{id}.agent37.app/v1/responses`
   with `stream: true`, read SSE (`response.output_text.delta`) to show the agent
   working; reuse `session_id` to continue the thread. This is where §10's PLANNER
   lives — "here's my drone video, build me a model" is a chat turn.
3. **The agent calls the GPU plane as a tool.** Bake the provider client into the
   image; the agent invokes it, the GPU job writes artifacts to S3, the viewer loads them.
4. **Custom image = your tools + skills.**
   `FROM ghcr.io/agent37-platform/hermes-base:latest`, install `ffmpeg` and your
   scripts into `/usr/local/bin`, keep the base ENTRYPOINT, publish with
   `npx agent37 templates build . --name drone3d-agent`. Install your skill folder
   into `~/.hermes/skills` over `exec` once the instance is running.
5. **Managed services, no keys.** Every instance gets `AGENT37_LLM_PROXY_URL`
   (OpenAI-compatible), `AGENT37_MANAGED_TOKEN`, `AGENT37_COMPOSIO_MCP_URL`
   (1,000+ apps), and `AGENT37_PERFLO_MCP_URL` (paid tools). Point the harness at
   these; BYOK is available.
6. **Scheduled runs** for batch jobs (e.g. "re-render every scene with the new trainer").
7. **White-label shell:** fork `agent37-platform/starter-kit` (sign-up, one agent
   per customer, chat, files, integrations) and rebrand — the fastest path to the
   app shell in Phase 1.

### 21.4 Phase mapping

| Phase | Agent37 work |
|---|---|
| 0 | Create a Hermes instance; confirm the agent can `exec` ffmpeg and reach an external GPU API |
| 1 | Build the shell from the starter-kit; one instance/user; chat via Agent API; jobs dispatched to Polycam/GPU externally |
| 2 | Custom image with ffmpeg + provider clients + skills; wire the tool calls |
| 5 | The planner/validator/recovery from §10 runs *inside* the harness; NL control via `/v1/responses` |
| 6 | Multi-tenancy = one instance per customer; per-instance budgets; `auto_sleep`; quotas |
| 7 | New features ship as new skills/tools installed into the instance |

### 21.5 Caveats to design around

- **No GPU** (repeated because it is the whole design constraint). Never schedule
  SfM or training on Agent37.
- **Small disks / 8 GB image cap** → keep media in object storage; only working
  state in the sandbox.
- **US-hosted today** → the §20 data-residency question is live for Indian
  customers; confirm region options before promising India-only hosting.
- **gVisor sandbox** → Docker-in-Docker needs the `agent37-ubuntu` **VM**
  template, not a default sandbox.
- **Young platform** → pin template versions (`agent37-hermes@<version>`) so every
  instance in a fleet runs an identical image.
- **Cost** → per-minute compute + disk until delete; `auto_sleep` and per-instance
  budgets are the controls. Approx rates: ~$0.0011/vCPU-hr, ~$0.00096/GB-hr RAM,
  ~$0.00012/GB-hr disk.
- **Untrusted workloads** → treat the sandbox as untrusted; secrets via instance
  env / BYOK; egress is public-internet only.

---

## 22. Sources & further reading

- Polycam Reconstruction API docs — https://poly.cam/docs/api/reconstruction
- Polycam Content Management API docs — https://poly.cam/docs/api
- Polycam Reconstruction API product page — https://poly.cam/reconstruction-api
- Polycam upload limits & Smart Keyframing — learn.poly.cam help center
- 3D Gaussian Splatting (Inria, SIGGRAPH 2023) — the original method
- gsplat (nerfstudio-project) — CUDA rasterization + training library; JMLR 2025
- Nerfstudio Splatfacto — https://docs.nerf.studio/nerfology/methods/splat.html
- COLMAP / GLOMAP — SfM reference implementations
- Brush — cross-platform (Metal/WebGPU) 3DGS trainer
- PlayCanvas `splat-transform` + Streamed SOG / LOD streaming
- PlayCanvas SuperSplat viewer — https://github.com/playcanvas/supersplat-viewer
- Babylon.js Gaussian Splatting + LOD streaming docs
- DroneSplat (CVPR 2025) — robust 3DGS from in-the-wild drone imagery
- Dynamic urban 3DGS from UAV full-motion video (ISPRS 2025)
- SkySplat (Blender add-on) — drone-video → COLMAP → 3DGS reference workflow
- RunPod vs Modal — serverless GPU tradeoffs for long reconstruction jobs
- AWS Deadline Cloud gsplat pipeline tutorial
- Agent37 docs (Sandbox API + Agent API) — https://www.agent37.com/docs
- Agent37 templates & custom images — https://www.agent37.com/docs/agents-api/templates
- Agent37 starter kit — https://github.com/agent37-platform/starter-kit

---

*End of plan.md — v1.2. Append features to §19; keep contracts (§6, §4) stable.*

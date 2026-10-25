# Drone Video → Interactive 3D Architecture Document

This architecture specifies how video footage uploaded from drones is converted into photorealistic, interactive 3D Gaussian Splats and textured polygon meshes.

## Pipeline Flow

```
+------------+       +-------------+       +-------------+       +---------------+
| S0: Ingest | ----> | S1: Extract | ----> | S2: Select  | ----> | S3: Poses     |
| ffprobe    |       | ffmpeg fps  |       | blur/stride |       | COLMAP/GLOMAP |
+------------+       +-------------+       +-------------+       +---------------+
                                                                         |
                                                                         v
+------------+       +-------------+       +-------------+       +---------------+
| S8: Publish| <---- | S7: Package | <---- | S6: Post    | <---- | S5: Train     |
| CDN/Web    |       | SOG / LOD   |       | clean/scale |       | gsplat/Polycam|
+------------+       +-------------+       +-------------+       +---------------+
```

## Contracts & Provider Models
- All pipeline stages strictly adhere to [`contracts/stages.py`](file:///contracts/stages.py)
- Providers implement [`backend/providers_base.py`](file:///backend/providers_base.py) for interchangeable:
  1. `PolycamProvider` (Buy track)
  2. `SelfHostedProvider` (Build track)
  3. `RouterProvider` (Hybrid track)

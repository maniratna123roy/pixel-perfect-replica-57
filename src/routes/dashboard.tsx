import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/dashboard")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Bird's Eye — Dashboard" },
      {
        name: "description",
        content:
          "Upload drone footage, monitor reconstruction, and explore 3D scenes in the Bird's Eye workspace.",
      },
      { property: "og:title", content: "Bird's Eye — Dashboard" },
      {
        property: "og:description",
        content: "Upload drone footage, monitor reconstruction, and explore 3D scenes.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LazyDashboard,
});

// The dashboard owns the WebGL viewport — it never renders on the server.
import { lazy, Suspense } from "react";

const DashboardShell = lazy(() =>
  import("@/components/dashboard/DashboardShell").then((m) => ({ default: m.DashboardShell })),
);

function LazyDashboard() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <DashboardShell />
    </Suspense>
  );
}

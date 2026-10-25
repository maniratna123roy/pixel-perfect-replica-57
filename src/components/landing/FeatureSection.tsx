import { Building2, Mountain, Rotate3d } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
}

const FEATURES: Feature[] = [
  {
    icon: Building2,
    title: "City Perspectives",
    description: "Explore urban landscapes, buildings, and city layouts from an aerial viewpoint.",
  },
  {
    icon: Mountain,
    title: "Terrain & Nature",
    description:
      "Experience the spatial relationships between mountains, terrain, and the built environment.",
  },
  {
    icon: Rotate3d,
    title: "Interactive 3D",
    description:
      "Move beyond flat footage and explore reconstructed environments through an interactive 3D view.",
  },
];

export function FeatureSection() {
  return (
    <section className="mx-auto max-w-6xl px-5 py-24 sm:px-8 sm:py-28">
      <div className="max-w-2xl">
        <h2 className="text-3xl font-medium tracking-tight text-foreground sm:text-4xl">
          A different way to see the world.
        </h2>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Transform aerial footage into immersive 3D environments. Discover the details,
          patterns, and perspectives hidden in the places around you.
        </p>
      </div>

      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, description }) => (
          <article
            key={title}
            className="glass rounded-2xl p-6 transition-colors duration-200 hover:border-white/20"
          >
            <Icon className="h-5 w-5 text-primary" strokeWidth={1.75} aria-hidden="true" />
            <h3 className="mt-4 text-lg font-medium text-foreground">{title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

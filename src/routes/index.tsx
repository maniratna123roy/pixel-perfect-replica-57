import { createFileRoute } from "@tanstack/react-router";
import { LandingNavbar } from "@/components/landing/LandingNavbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { FeatureSection } from "@/components/landing/FeatureSection";
import { HowToSection } from "@/components/landing/HowToSection";
import { LandingFooter } from "@/components/landing/LandingFooter";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Bird's Eye — The world, from a different perspective" },
      {
        name: "description",
        content:
          "Turn aerial footage into immersive 3D environments. Explore cities, terrain, and places from a new perspective.",
      },
      { property: "og:title", content: "Bird's Eye — The world, from a different perspective" },
      {
        property: "og:description",
        content: "Turn aerial footage into immersive 3D environments.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LandingPage,
});

function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <LandingNavbar />
      <main>
        <HeroSection />
        <FeatureSection />
        <HowToSection />
      </main>
      <LandingFooter />
    </div>
  );
}

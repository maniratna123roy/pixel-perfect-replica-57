import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { HERO_VIDEO_SRC } from "@/config";

/**
 * Full-screen cinematic hero. Aerial night-city footage fills the viewport;
 * a uniform dark scrim keeps the headline readable. If the video fails or
 * the visitor prefers reduced motion, a solid dark fallback remains.
 */
export function HeroSection() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [allowMotion, setAllowMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!media.matches) setAllowMotion(true);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !allowMotion) return;
    const attempt = () => video.play().catch(() => undefined);
    attempt();
    // A stalled load (network) leaves the dark fallback visible beneath.
    const timer = window.setTimeout(() => {
      if (video.readyState < 2) video.load();
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [allowMotion]);

  return (
    <section className="relative flex min-h-[100svh] items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-viewport" aria-hidden="true" />
      {allowMotion ? (
        <video
          ref={videoRef}
          className="absolute inset-0 h-full w-full object-cover"
          src={HERO_VIDEO_SRC}
          muted
          loop
          playsInline
          autoPlay
          preload="auto"
          aria-hidden="true"
          tabIndex={-1}
        />
      ) : null}
      {/* Uniform scrim — solid black translucency, no gradient. */}
      <div className="absolute inset-0 bg-black/30" aria-hidden="true" />

      <div className="relative z-10 mx-auto max-w-3xl px-6 text-center">
        <h1 className="font-display text-[clamp(3rem,9vw,6.5rem)] italic leading-[1.04] tracking-[-0.01em] text-foreground">
          The world,
          <br />
          from a different perspective.
        </h1>
        <p className="mx-auto mt-6 max-w-md text-base text-foreground/80 sm:text-lg">
          Turn aerial footage into worlds you can explore.
        </p>
        <div className="mt-9">
          <Link to="/dashboard" className="btn-glass px-7 py-3 text-base">
            Explore Bird&rsquo;s Eye
          </Link>
        </div>
      </div>
    </section>
  );
}

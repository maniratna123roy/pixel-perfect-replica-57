import { Link } from "@tanstack/react-router";

interface Step {
  number: string;
  title: string;
  description: string;
}

const STEPS: Step[] = [
  {
    number: "01",
    title: "Upload your footage",
    description: "Select a drone video of the environment you want to reconstruct.",
  },
  {
    number: "02",
    title: "Reconstruct the scene",
    description: "Process the footage through the reconstruction pipeline to generate a 3D representation.",
  },
  {
    number: "03",
    title: "Explore in 3D",
    description: "Navigate the reconstructed environment and inspect it from different viewpoints.",
  },
];

export function HowToSection() {
  return (
    <section id="how-to" className="scroll-mt-20 border-t border-border">
      <div className="mx-auto max-w-6xl px-5 py-24 sm:px-8 sm:py-28">
        <h2 className="text-3xl font-medium tracking-tight text-foreground sm:text-4xl">
          Three steps. A new perspective.
        </h2>

        <ol className="mt-14 divide-y divide-border border-y border-border">
          {STEPS.map((step) => (
            <li key={step.number} className="grid gap-2 py-8 sm:grid-cols-[80px_1fr_1.2fr] sm:items-baseline sm:gap-6">
              <span className="font-display text-3xl italic text-muted-foreground">
                {step.number}
              </span>
              <h3 className="text-lg font-medium text-foreground">{step.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{step.description}</p>
            </li>
          ))}
        </ol>

        <div className="mt-12">
          <Link to="/dashboard" className="btn-primary-solid">
            Start Exploring
          </Link>
        </div>
      </div>
    </section>
  );
}

import { Link } from "@tanstack/react-router";

export function LandingNavbar() {
  return (
    <header className="fixed inset-x-0 top-0 z-30">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8"
      >
        <Link to="/" className="text-[17px] font-medium tracking-tight text-foreground">
          bird&rsquo;s eye
        </Link>
        <div className="flex items-center gap-2.5">
          <Link to="/dashboard" className="btn-glass">
            Try Us
          </Link>
          <a href="#how-to" className="btn-glass">
            How to use
          </a>
        </div>
      </nav>
    </header>
  );
}

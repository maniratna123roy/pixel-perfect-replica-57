export function LandingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div>
          <p className="text-sm font-medium text-foreground">bird&rsquo;s eye</p>
          <p className="mt-1 text-sm text-muted-foreground">A new perspective on the world.</p>
        </div>
        <p className="text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} Bird&rsquo;s Eye. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

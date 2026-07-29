export function youtubeWatchUrl(youtubeVideoId: string): string {
  return `https://www.youtube.com/watch?v=${youtubeVideoId}`;
}

/**
 * Always a real <a target="_blank" rel="noopener noreferrer"> — never routed
 * through next/navigation — so it never competes with internal Link clicks.
 */
export function ExternalLink({
  href,
  label,
  variant = "icon",
}: {
  href: string;
  label: string;
  variant?: "button" | "icon";
}) {
  if (variant === "button") {
    return (
      <a className="button externalCta" href={href} target="_blank" rel="noopener noreferrer">
        {label}
        <span className="externalIcon" aria-hidden="true">
          ↗
        </span>
      </a>
    );
  }
  return (
    <a className="externalIconLink" href={href} target="_blank" rel="noopener noreferrer" title={label} aria-label={label}>
      <span aria-hidden="true">↗</span>
    </a>
  );
}

"use client";

import { useState } from "react";

export function ExpandableDescription({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) {
    return <p className="muted">Brak opisu filmu.</p>;
  }
  const isLong = text.length > 220;
  return (
    <div className="expandableDescription">
      <p className={expanded || !isLong ? "muted" : "muted clamped"}>{text}</p>
      {isLong ? (
        <button type="button" className="textLinkButton" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Pokaż mniej" : "Pokaż więcej"}
        </button>
      ) : null}
    </div>
  );
}

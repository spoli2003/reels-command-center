import type { PlatformKey } from "../lib/platform-api";

export function AudienceGain({ platform, value }: { platform: PlatformKey; value?: number | null }) {
  const noun = platform === "youtube" ? "subskrybentów" : "obserwujących";
  if (value === null || value === undefined) {
    const source = platform === "youtube" ? "YouTube" : platform === "facebook" ? "Facebooka" : "Instagrama";
    return (
      <span className="audienceGain unavailable" title={`Połączone API ${source} nie zwróciło liczby pozyskanych ${noun} dla tego materiału.`}>
        Pozyskani: brak danych
      </span>
    );
  }
  return <span className="audienceGain">+{value.toLocaleString("pl-PL")} {noun}</span>;
}

import { describe, expect, it } from "vitest";

import { toWellFormedText } from "./platform-api";

describe("platform API text normalization", () => {
  it("preserves valid emoji surrogate pairs", () => {
    expect(toWellFormedText("Działa 🤝")).toBe("Działa 🤝");
  });

  it("replaces unpaired surrogates before React hydration", () => {
    expect(toWellFormedText(`Tytuł ${String.fromCharCode(0xd83e)} materiału`)).toBe("Tytuł � materiału");
    expect(toWellFormedText(`Komentarz ${String.fromCharCode(0xdd10)}`)).toBe("Komentarz �");
  });
});

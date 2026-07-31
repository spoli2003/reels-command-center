import { describe, expect, it } from "vitest";

import { truncateTitle } from "./youtube-metrics";

describe("truncateTitle", () => {
  it("never cuts an emoji surrogate pair", () => {
    const title = `${"a".repeat(45)}🤝 dalszy tekst`;

    const truncated = truncateTitle(title, 47);

    expect(truncated).toBe(`${"a".repeat(45)}🤝…`);
    expect(truncated).not.toContain("�");
  });
});

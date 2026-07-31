import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AudienceGain } from "./audience-gain";

afterEach(cleanup);

describe("AudienceGain", () => {
  it("renders an honest unavailable state for a legacy missing field", () => {
    render(<AudienceGain platform="facebook" value={undefined} />);
    expect(screen.getByText("Pozyskani: brak danych")).toBeTruthy();
  });

  it("formats a real audience gain", () => {
    render(<AudienceGain platform="youtube" value={105} />);
    expect(screen.getByText(/\+105 subskrybentów/)).toBeTruthy();
  });
});

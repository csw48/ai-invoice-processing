import { describe, expect, it } from "vitest";
import { highlightCandidates } from "./invoice-pdf-viewer";

describe("highlightCandidates", () => {
  it("includes localized fixed-decimal variants for extracted amount values", () => {
    expect(highlightCandidates("149.44")).toEqual(
      expect.arrayContaining(["149.44", "149,44"])
    );
    expect(highlightCandidates("121.5")).toEqual(
      expect.arrayContaining(["121.5", "121.50", "121,5", "121,50"])
    );
  });
});

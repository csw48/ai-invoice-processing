import { describe, expect, it } from "vitest";
import { uploadButtonLabel } from "./upload-panel";

describe("uploadButtonLabel", () => {
  it("describes the idle upload state", () => {
    expect(uploadButtonLabel("idle")).toBe("Upload invoice");
  });

  it("describes the uploading state", () => {
    expect(uploadButtonLabel("uploading")).toBe("Processing...");
  });
});

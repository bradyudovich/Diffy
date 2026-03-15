/**
 * scoreUtils.test.ts – Unit tests for the scoreUtils utility functions.
 *
 * Run with:  npm test
 */
import { describe, it, expect } from "vitest";
import {
  parseSummary,
  deriveDataScore,
  deriveUserRightsScore,
  deriveReadabilityScore,
  deriveOverallScore,
  benchmarkLabel,
  mean,
} from "./scoreUtils";

// ---------------------------------------------------------------------------
// parseSummary
// ---------------------------------------------------------------------------
describe("parseSummary", () => {
  it("parses a standard bracketed summary into sections", () => {
    const input = "[Data Rights]: Users retain ownership. [AI Usage]: Outputs may be inaccurate.";
    const result = parseSummary(input);
    expect(result["Data Rights"]).toBe("Users retain ownership.");
    expect(result["AI Usage"]).toBe("Outputs may be inaccurate.");
  });

  it("returns an empty object for an empty string", () => {
    expect(parseSummary("")).toEqual({});
  });

  it("trims whitespace from keys and values", () => {
    const result = parseSummary("[ Privacy ]:   Some data collected.");
    expect(result["Privacy"]).toBe("Some data collected.");
  });

  it("handles a single section without trailing bracket", () => {
    const result = parseSummary("[Liability]: Company disclaims all liability.");
    expect(result["Liability"]).toBe("Company disclaims all liability.");
  });

  it("handles three sections correctly", () => {
    const input =
      "[Privacy]: Data is shared. [DataOwnership]: Users own content. [UserRights]: Arbitration required.";
    const result = parseSummary(input);
    expect(Object.keys(result)).toHaveLength(3);
    expect(result["Privacy"]).toBe("Data is shared.");
    expect(result["DataOwnership"]).toBe("Users own content.");
    expect(result["UserRights"]).toBe("Arbitration required.");
  });
});

// ---------------------------------------------------------------------------
// deriveDataScore
// ---------------------------------------------------------------------------
describe("deriveDataScore", () => {
  it("returns 75 for an empty string", () => {
    expect(deriveDataScore("")).toBe(75);
  });

  it("reduces score when negative data terms are present", () => {
    const score = deriveDataScore(
      "The company may sell your data to third party advertisers."
    );
    expect(score).toBeLessThan(75);
  });

  it("increases score when positive data terms are present", () => {
    const score = deriveDataScore(
      "Users retain ownership of their data. We do not sell it."
    );
    expect(score).toBeGreaterThan(75);
  });

  it("clamps score to [10, 100]", () => {
    // Pile on many negative terms
    const veryBad =
      "sell selling third party third-party share personal collect surveillance biometric transfer monetize advertising ads";
    const score = deriveDataScore(veryBad.repeat(5));
    expect(score).toBeGreaterThanOrEqual(10);
    expect(score).toBeLessThanOrEqual(100);
  });
});

// ---------------------------------------------------------------------------
// deriveUserRightsScore
// ---------------------------------------------------------------------------
describe("deriveUserRightsScore", () => {
  it("returns 75 for an empty string", () => {
    expect(deriveUserRightsScore("")).toBe(75);
  });

  it("reduces score for arbitration clauses", () => {
    const score = deriveUserRightsScore(
      "All disputes are subject to mandatory arbitration. Class action rights are waived."
    );
    expect(score).toBeLessThan(75);
  });

  it("increases score for user-friendly terms", () => {
    const score = deriveUserRightsScore(
      "Users retain full rights to their data. GDPR compliant."
    );
    expect(score).toBeGreaterThan(75);
  });

  it("clamps score to [10, 100]", () => {
    const veryBad =
      "arbitration class action waive mandatory indemnify liability limited no liability hold harmless forfeit";
    const score = deriveUserRightsScore(veryBad.repeat(5));
    expect(score).toBeGreaterThanOrEqual(10);
    expect(score).toBeLessThanOrEqual(100);
  });
});

// ---------------------------------------------------------------------------
// deriveReadabilityScore
// ---------------------------------------------------------------------------
describe("deriveReadabilityScore", () => {
  it("returns 70 for an empty string", () => {
    expect(deriveReadabilityScore("")).toBe(70);
  });

  it("reduces score for legalese terms", () => {
    const score = deriveReadabilityScore(
      "Notwithstanding the aforementioned provisions, hereinafter defined pursuant to this agreement."
    );
    expect(score).toBeLessThan(70);
  });

  it("applies a length penalty for very long text", () => {
    const longText = "This is a reasonably clear sentence. ".repeat(30);
    const shortText = "This is a clear sentence.";
    expect(deriveReadabilityScore(longText)).toBeLessThanOrEqual(
      deriveReadabilityScore(shortText)
    );
  });

  it("clamps score to [10, 100]", () => {
    const badText =
      "notwithstanding hereinafter indemnification pursuant aforementioned thereto hereof whereas".repeat(10);
    const score = deriveReadabilityScore(badText);
    expect(score).toBeGreaterThanOrEqual(10);
    expect(score).toBeLessThanOrEqual(100);
  });
});

// ---------------------------------------------------------------------------
// deriveOverallScore
// ---------------------------------------------------------------------------
describe("deriveOverallScore", () => {
  it("returns a number between 0 and 100", () => {
    const score = deriveOverallScore(
      "[Data Rights]: Users retain ownership. [Liability]: Arbitration required."
    );
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(100);
  });

  it("is lower for a TOS with many concerning terms", () => {
    const concerningScore = deriveOverallScore(
      "Company may sell data to third parties. Mandatory arbitration. Class action waived. No liability."
    );
    const cleanScore = deriveOverallScore(
      "Users retain ownership. We do not sell data."
    );
    expect(concerningScore).toBeLessThan(cleanScore);
  });
});

// ---------------------------------------------------------------------------
// benchmarkLabel
// ---------------------------------------------------------------------------
describe("benchmarkLabel", () => {
  it("returns 'Top Tier' when score is well above average", () => {
    expect(benchmarkLabel(95, 70)).toBe("Top Tier");
  });

  it("returns 'Above Average' when moderately above average", () => {
    expect(benchmarkLabel(80, 70)).toBe("Above Average");
  });

  it("returns 'Average' when close to average", () => {
    expect(benchmarkLabel(72, 70)).toBe("Average");
  });

  it("returns 'Below Average' when moderately below average", () => {
    expect(benchmarkLabel(58, 70)).toBe("Below Average");
  });

  it("returns 'Needs Improvement' when far below average", () => {
    expect(benchmarkLabel(40, 70)).toBe("Needs Improvement");
  });
});

// ---------------------------------------------------------------------------
// mean
// ---------------------------------------------------------------------------
describe("mean", () => {
  it("returns 0 for an empty array", () => {
    expect(mean([])).toBe(0);
  });

  it("returns the value itself for a single-element array", () => {
    expect(mean([42])).toBe(42);
  });

  it("correctly computes the mean of multiple values", () => {
    expect(mean([10, 20, 30])).toBeCloseTo(20);
    expect(mean([100, 80, 60])).toBeCloseTo(80);
  });
});

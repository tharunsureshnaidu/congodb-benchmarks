import fs from "fs";
import path from "path";

export type Stats = { p50: number | null; p95: number | null; min?: number; max?: number; n?: number };

export type PlatformResult = {
  platform: string;
  kind: string;
  loading?: {
    node_count: number;
    relationship_count: number;
    wall_clock_s: number;
    nodes_per_s: number;
    relationships_per_s: number;
  };
  traversals?: { hop_1: Stats; hop_2: Stats; hop_3: Stats };
  lookups?: { point_lookup: Stats; filtered_lookup: Stats };
  aggregation?: Stats;
  mixed_workload?: Array<{
    concurrency: number;
    write_ratio: number;
    duration_s: number;
    total_ops: number;
    throughput_qps: number;
  }>;
};

export type Summary = Record<string, PlatformResult>;

// Falls back to the example/placeholder file when no live benchmark has been
// run yet, clearly flagged via `isPlaceholder` so the UI never presents
// invented numbers as real measurements.
export function loadSummary(): { summary: Summary; isPlaceholder: boolean } {
  const resultsDir = path.join(process.cwd(), "..", "results");
  const realPath = path.join(resultsDir, "summary.json");
  const examplePath = path.join(resultsDir, "summary.example.json");

  if (fs.existsSync(realPath)) {
    return { summary: JSON.parse(fs.readFileSync(realPath, "utf-8")), isPlaceholder: false };
  }
  return { summary: JSON.parse(fs.readFileSync(examplePath, "utf-8")), isPlaceholder: true };
}

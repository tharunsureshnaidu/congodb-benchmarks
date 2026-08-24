import React from "react";
import { loadSummary, Stats } from "@/lib/results";
import { PLATFORM_META, PLATFORM_ORDER } from "@/lib/platforms";

function fmt(n: number | null | undefined, unit = "") {
  if (n === null || n === undefined) return "—";
  return `${n.toFixed(1)}${unit}`;
}

function BarCell({ value, max, unit }: { value: number | null | undefined; max: number; unit: string }) {
  if (value === null || value === undefined) return <td>—</td>;
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <td>
      <div className="bar-cell">
        <span>{fmt(value, unit)}</span>
        <div className="bar-track"><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
      </div>
    </td>
  );
}

function LatencyTable({ title, rows, platforms }: {
  title: string;
  rows: Array<{ label: string; getStats: (p: string) => Stats | undefined }>;
  platforms: string[];
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Query</th>
            {platforms.map((p) => (
              <th key={p} colSpan={2}>{PLATFORM_META[p]?.label ?? p}</th>
            ))}
          </tr>
          <tr>
            <th></th>
            {platforms.map((p) => (
              <React.Fragment key={p}>
                <th>p50 (ms)</th>
                <th>p95 (ms)</th>
              </React.Fragment>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              {platforms.map((p) => {
                const s = row.getStats(p);
                return (
                  <React.Fragment key={p}>
                    <td>{fmt(s?.p50)}</td>
                    <td>{fmt(s?.p95)}</td>
                  </React.Fragment>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Page() {
  const { summary, isPlaceholder } = loadSummary();
  const platforms = PLATFORM_ORDER.filter((p) => summary[p]);
  const maxLoadRate = Math.max(...platforms.map((p) => summary[p]?.loading?.relationships_per_s ?? 0), 1);
  const maxThroughput = Math.max(
    ...platforms.flatMap((p) => summary[p]?.mixed_workload?.map((m) => m.throughput_qps) ?? []),
    1
  );

  return (
    <main>
      <h1>Graph Database Cloud Benchmarks</h1>
      <p className="subtitle">
        CognoDB Cloud vs. Neo4j AuraDB Free, Memgraph Cloud, FalkorDB Cloud, and ArangoDB Oasis.
      </p>

      {isPlaceholder && (
        <div className="banner">
          Showing placeholder data from <code>results/summary.example.json</code> — no live benchmark
          has been run yet. Run <code>scripts/run_all.sh</code> against real platform accounts to
          generate <code>results/summary.json</code>, which this page prefers automatically.
        </div>
      )}

      <h2>Instance specs (free/entry tier)</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Platform</th><th>vCPU</th><th>RAM</th><th>Storage</th><th>Query language</th></tr>
          </thead>
          <tbody>
            {platforms.map((p) => {
              const m = PLATFORM_META[p];
              return (
                <tr key={p}>
                  <td>{m.label}</td><td>{m.vcpu}</td><td>{m.ram}</td><td>{m.storage}</td><td>{m.queryLanguage}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2>Data loading throughput</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Platform</th><th>Nodes</th><th>Relationships</th><th>Wall clock</th><th>Rels/sec</th></tr>
          </thead>
          <tbody>
            {platforms.map((p) => {
              const l = summary[p]?.loading;
              return (
                <tr key={p}>
                  <td>{PLATFORM_META[p].label}</td>
                  <td>{l?.node_count ?? "—"}</td>
                  <td>{l?.relationship_count ?? "—"}</td>
                  <td>{l ? `${l.wall_clock_s.toFixed(1)}s` : "—"}</td>
                  <BarCell value={l?.relationships_per_s} max={maxLoadRate} unit="" />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2>Traversal latency (1/2/3-hop)</h2>
      <LatencyTable
        title="Traversals"
        platforms={platforms}
        rows={[
          { label: "1-hop", getStats: (p) => summary[p]?.traversals?.hop_1 },
          { label: "2-hop", getStats: (p) => summary[p]?.traversals?.hop_2 },
          { label: "3-hop", getStats: (p) => summary[p]?.traversals?.hop_3 },
        ]}
      />

      <h2>Lookups</h2>
      <LatencyTable
        title="Lookups"
        platforms={platforms}
        rows={[
          { label: "Point lookup (indexed id)", getStats: (p) => summary[p]?.lookups?.point_lookup },
          { label: "Filtered lookup (indexed department)", getStats: (p) => summary[p]?.lookups?.filtered_lookup },
        ]}
      />

      <h2>Aggregation (group-by department)</h2>
      <LatencyTable
        title="Aggregation"
        platforms={platforms}
        rows={[{ label: "COUNT ... GROUP BY department", getStats: (p) => summary[p]?.aggregation }]}
      />

      <h2>Mixed read/write throughput (concurrency sweep, 90/10 read/write)</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Platform</th>
              {(summary[platforms[0]]?.mixed_workload ?? []).map((m) => (
                <th key={m.concurrency}>{m.concurrency} client{m.concurrency > 1 ? "s" : ""}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {platforms.map((p) => (
              <tr key={p}>
                <td>{PLATFORM_META[p].label}</td>
                {(summary[p]?.mixed_workload ?? []).map((m) => (
                  <BarCell key={m.concurrency} value={m.throughput_qps} max={maxThroughput} unit=" qps" />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer>
        Full methodology, dataset details, and honest caveats live in the repo README.
      </footer>
    </main>
  );
}

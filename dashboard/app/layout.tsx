import "./globals.css";

export const metadata = {
  title: "Graph DB Cloud Benchmarks",
  description: "CognoDB Cloud vs. Neo4j AuraDB, Memgraph Cloud, FalkorDB Cloud, and ArangoDB Oasis",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

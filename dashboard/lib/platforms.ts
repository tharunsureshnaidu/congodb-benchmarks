export type PlatformMeta = {
  key: string;
  label: string;
  vcpu: string;
  ram: string;
  storage: string;
  queryLanguage: string;
};

// Advertised free/entry-tier specs, as documented in the README methodology.
// Keep this in sync with README.md's resource table if you change tiers.
export const PLATFORM_META: Record<string, PlatformMeta> = {
  cognodb: {
    key: "cognodb",
    label: "CognoDB Cloud (c0 free)",
    vcpu: "0.5 (burstable)",
    ram: "256 MB",
    storage: "1 GB",
    queryLanguage: "Cypher (Bolt)",
  },
  aura: {
    key: "aura",
    label: "Neo4j AuraDB Free",
    vcpu: "0.5 (shared/burstable)",
    ram: "256 MB",
    storage: "1 GB",
    queryLanguage: "Cypher (Bolt)",
  },
  memgraph: {
    key: "memgraph",
    label: "Memgraph Cloud (entry)",
    vcpu: "0.5",
    ram: "256 MB",
    storage: "1 GB",
    queryLanguage: "Cypher (Bolt)",
  },
  falkordb: {
    key: "falkordb",
    label: "FalkorDB Cloud (free tier)",
    vcpu: "0.5",
    ram: "256 MB",
    storage: "1 GB",
    queryLanguage: "openCypher (FalkorDB client)",
  },
  arango: {
    key: "arango",
    label: "ArangoDB Oasis (free trial tier)",
    vcpu: "0.5",
    ram: "256 MB",
    storage: "1 GB",
    queryLanguage: "AQL",
  },
};

export const PLATFORM_ORDER = ["cognodb", "aura", "memgraph", "falkordb", "arango"];

// Knowledge sources, search, settings, runs and uploads.

export type KnowledgeCrawl = {
  fetch_every_hours: number;
  extractor: string | null;
  enabled: boolean;
  last_attempt_at: string | null;
  last_error: string | null;
};

export type KnowledgeSource = {
  id: string;
  key: string;
  url: string | null;
  title: string | null;
  category: string;
  public: boolean;
  version_id: string | null;
  content_hash: string | null;
  embedding_model: string | null;
  chunk_count: number;
  fetched_at: string | null;
  updated_at: string | null;
  crawl: KnowledgeCrawl | null;
};

// One page of a source's full text, from GET /knowledge/sources/<key>.
export type KnowledgePassage = { id: string; ordinal: number; text: string };

export type KnowledgeSourceText = {
  source: KnowledgeSource & { own: boolean; text_chars: number | null };
  passages: KnowledgePassage[];
  focus: string[];
  offset: number;
  next_offset: number | null;
  total: number;
};

export type SearchResult = {
  chunk_id: string;
  source_key: string;
  title: string | null;
  url: string | null;
  category: string;
  public: boolean;
  content: string;
  score: number;
  fetched_at: string | null;
};

export type SearchResponse = { results: SearchResult[]; dense: boolean };

export type KnowledgeMode = 'hybrid' | 'text' | 'vector';

export type KnowledgeTuning = {
  chunk_chars: number;
  chunk_overlap: number;
  mode: KnowledgeMode;
  top_k: number;
  window: number;
  max_distance: number;
  rrf_k: number;
};

export type KnowledgeSettings = {
  settings: KnowledgeTuning;
  defaults: KnowledgeTuning;
  embeddings: { configured: boolean; model: string | null; status?: EmbeddingStatus };
};

// Passages of the org's sources by embedding model. stale passages are found by text search only.
export type EmbeddingStatus = {
  model: string | null;
  passages: number;
  embedded: number;
  stale: number;
  models: { model: string | null; passages: number }[];
};

export type KnowledgeRun = {
  id: number;
  source_key: string;
  kind: 'crawl' | 'upload';
  started_at: string;
  duration_ms: number;
  changed: boolean;
  chunks: number | null;
  error: string | null;
};

export type UploadResult = {
  files: { file: string; key: string; changed: boolean; chunks: number; error: string | null }[];
  indexed: number;
  unchanged: number;
  failed: number;
};

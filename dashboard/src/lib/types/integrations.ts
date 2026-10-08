// One key of an integration. Values are never sent back; set says whether the org saved one.
export type IntegrationField = {
  name: string;
  label: string;
  hint: string;
  kind: 'text' | 'json';
  set: boolean;
  updated_at: string | null;
};

// An outside service. source is org (the org's keys), deployment (the default in .env) or null (not connected).
export type Integration = {
  key: string;
  title: string;
  description: string;
  docs: string | null;
  fields: IntegrationField[];
  editable: boolean;
  source: 'org' | 'deployment' | null;
  testable: boolean;
  used_by: string[];
};

export type IntegrationList = { integrations: Integration[]; secrets_key: boolean };

export type IntegrationTest = { ok: boolean; message: string };

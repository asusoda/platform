// Hosting providers that pods and apps run on.

// A provider from GET /api/dashboard/<org>/hosting/providers. integration is its key on the Integrations page.
export type HostingProvider = {
  name: string;
  title: string;
  integration: string;
  configured: boolean;
};

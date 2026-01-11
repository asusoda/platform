// Frontend configuration
const isLocalhost =
  typeof window !== 'undefined' &&
  ['localhost', '127.0.0.1', '0.0.0.0'].includes(window.location.hostname);

const envApiUrl = process.env.REACT_APP_API_URL;

// Safety: when the UI is served from localhost, default to localhost API.
// This avoids accidentally hitting production (and producing production OAuth redirects).
const defaultApiUrl = isLocalhost ? 'http://localhost:8000' : 'https://api.thesoda.io';

// If someone accidentally built the web image with the production API URL but is running locally,
// prefer the local API unless they explicitly override REACT_APP_API_URL to a localhost URL.
const effectiveApiUrl =
  isLocalhost && envApiUrl && envApiUrl.includes('thesoda.io') ? defaultApiUrl : (envApiUrl || defaultApiUrl);

const config = {
  // API Base URL - removes any trailing slash for consistency
  apiUrl: effectiveApiUrl.replace(/\/$/, ''),
  tokenRefreshInterval: 15 * 60 * 1000, // 15 minutes in milliseconds
};

export default config; 

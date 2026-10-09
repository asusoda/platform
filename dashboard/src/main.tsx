import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './index.css';
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { App } from './app';
import { ApiError } from './lib/api';
import { reportError, startMonitoring } from './lib/monitoring';
import { applyTheme, storedTheme } from './lib/theme';

applyTheme(storedTheme());
void startMonitoring();

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: (error, query) => reportError(error, `query ${String(query.queryKey[0])}`) }),
  mutationCache: new MutationCache({ onError: (error) => reportError(error, 'mutation') }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
});

queryClient.getQueryCache().subscribe((event) => {
  const error = event.query.state.error;
  if (error instanceof ApiError && error.status === 401 && location.pathname !== '/login' && !location.pathname.startsWith('/store/')) location.assign('/login');
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);

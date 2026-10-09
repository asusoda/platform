// Measures the dashboard with long lists: largeFixtures() in fixtures.mjs answers every API call.
// Run with npm run perf. It builds, serves dist/ with vite preview and prints the time of each step and the
// long tasks (main thread blocked for 50 ms or more) during the step. Needs Playwright with Chromium, as screenshots.mjs.

import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { preview } from 'vite';
import { largeFixtures, ORG } from './fixtures.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PORT = 4186;
const base = `http://localhost:${PORT}`;

async function loadPlaywright() {
  try {
    return await import('playwright');
  } catch {
    const globalRoot = execSync('npm root -g', { encoding: 'utf8' }).trim();
    return createRequire(join(globalRoot, 'noop.js'))('playwright');
  }
}

// Long tasks and slow frames since the last call to take().
async function take(page) {
  return page.evaluate(() => {
    const tasks = window.__longTasks.splice(0);
    return {
      longTasks: tasks.length,
      blockedMs: Math.round(tasks.reduce((n, d) => n + d, 0)),
      maxTaskMs: Math.round(Math.max(0, ...tasks)),
    };
  });
}

async function step(page, name, run, results) {
  await take(page);
  const start = Date.now();
  await run();
  const ms = Date.now() - start;
  await page.waitForTimeout(100);
  results.push({ step: name, ms, ...(await take(page)) });
}

// Scrolls the page to the end in steps and returns the longest gap between two frames.
async function scrollToEnd(page) {
  return page.evaluate(async () => {
    let worst = 0;
    let last = performance.now();
    const target = document.documentElement.scrollHeight - innerHeight;
    for (let y = 0; y <= target + 400; y += 400) {
      scrollTo(0, y);
      await new Promise((done) => requestAnimationFrame(done));
      const now = performance.now();
      worst = Math.max(worst, now - last);
      last = now;
    }
    return Math.round(worst);
  });
}

async function main() {
  const { chromium } = await loadPlaywright();
  const server = await preview({ root, preview: { port: PORT, strictPort: true }, logLevel: 'warn' });
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined });
  const results = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript(() => {
      localStorage.setItem('platform.access_token', 'perf-placeholder');
      window.__longTasks = [];
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) window.__longTasks.push(entry.duration);
      }).observe({ type: 'longtask', buffered: true });
    });
    const data = largeFixtures();
    await context.route('**/api/**', (route) => {
      const url = new URL(route.request().url());
      if (url.origin === base) return route.fallback();
      const body = data[url.pathname];
      if (body === undefined) return route.fulfill({ status: 404, json: { error: `No fixture for ${url.pathname}` } });
      return route.fulfill({ status: 200, json: body });
    });
    const page = await context.newPage();
    const go = (path) => page.goto(`${base}/${ORG.prefix}/${path}`);

    await go('');
    await page.waitForLoadState('networkidle');

    await step(page, 'knowledge: open', async () => {
      await go('knowledge');
      await page.locator('tbody tr').first().waitFor();
    }, results);
    await step(page, 'knowledge: domain filter', async () => {
      await page.getByRole('tab', { name: /^club/ }).click();
      await page.getByText(/^(?!2,?000 )[\d,]+ of 2,?000 sources/).waitFor();
    }, results);
    await step(page, 'knowledge: other domain', async () => {
      await page.getByRole('tab', { name: /^docs/ }).click();
      await page.getByText(/^(?!334 )[\d,]+ of 2,?000 sources/).waitFor();
    }, results);
    const sourceSearch = page.getByLabel('Find a source');
    if (await sourceSearch.count()) {
      await step(page, 'knowledge: type in search', async () => {
        await sourceSearch.pressSequentially('safety', { delay: 30 });
        await page.waitForFunction(() => document.querySelectorAll('tbody tr').length < 100);
      }, results);
      await sourceSearch.fill('');
    }
    await page.getByRole('tab', { name: /^All domains/ }).click();
    let frame = 0;
    await step(page, 'knowledge: scroll to end', async () => {
      frame = await scrollToEnd(page);
    }, results);
    results[results.length - 1].worstFrameMs = frame;

    await step(page, 'points: open', async () => {
      await go('points');
      await page.locator('tbody tr').first().waitFor();
    }, results);
    await step(page, 'points: type in search', async () => {
      await page.getByLabel('Find a member').pressSequentially('lena park', { delay: 30 });
      await page.waitForFunction(() => document.querySelectorAll('tbody tr').length < 200);
    }, results);
    await page.getByLabel('Find a member').fill('');
    await step(page, 'points: scroll to end', async () => {
      frame = await scrollToEnd(page);
    }, results);
    results[results.length - 1].worstFrameMs = frame;

    await step(page, 'activity: open 1,000 entries', async () => {
      await go('activity');
      await page.locator('main li').first().waitFor();
    }, results);
    await step(page, 'store: open 600 orders', async () => {
      await go('store?tab=orders');
      await page.locator('tbody tr').first().waitFor();
    }, results);
    await context.close();
  } finally {
    await browser.close();
    await new Promise((done) => server.httpServer.close(done));
  }
  console.table(results);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

/**
 * Talks to the Home Assistant the repository's docker-compose provides.
 *
 * The suite reuses that instance instead of booting one of its own. On a fresh
 * clone (CI, a new machine) the instance is empty, so global setup brings it to
 * the state the specs need: it onboards the test user and adds one config
 * entry, which is what makes Home Assistant load the integration at all. On an
 * instance that already has both (the manual playground) it changes nothing.
 * Everything the suite writes goes into dashboards of its own.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
export const E2E_DIR = resolve(here, '..');
const REPO_ROOT = resolve(E2E_DIR, '../..');
const TOKEN_FILE = resolve(E2E_DIR, '.auth.json');

/** Read from the compose file so the suite cannot drift from the environment. */
function portFromCompose(): string {
  const compose = readFileSync(resolve(REPO_ROOT, 'docker-compose.yml'), 'utf8');
  const match = compose.match(/'(\d+):8123'/) ?? compose.match(/"(\d+):8123"/);
  if (!match) throw new Error('No published Home Assistant port found in docker-compose.yml');
  return match[1];
}

export const PORT = process.env.HA_E2E_PORT ?? portFromCompose();
export const BASE_URL = `http://127.0.0.1:${PORT}`;
export const USERNAME = process.env.HA_E2E_USER ?? 'admin';
export const PASSWORD = process.env.HA_E2E_PASSWORD ?? 'password';

/** Brings the repository's own compose environment up if it is not running. */
export function ensureRunning(): void {
  execFileSync('docker', ['compose', 'up', '-d'], { cwd: REPO_ROOT, stdio: 'inherit' });
}

export async function waitForFrontend(timeoutMs = 180_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      // Not /api/onboarding: that endpoint is gone once onboarding is done.
      const res = await fetch(`${BASE_URL}/manifest.json`);
      if (res.ok) return;
    } catch {
      // not listening yet
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`Home Assistant did not answer at ${BASE_URL} within ${timeoutMs}ms`);
}

/**
 * Onboards a brand-new instance through its own API, the way the onboarding
 * wizard does. A no-op once onboarding is done (the endpoint answers 404 then).
 */
export async function onboardIfNeeded(): Promise<void> {
  // The HTTP server can answer /manifest.json before the onboarding views exist.
  let status = await fetch(`${BASE_URL}/api/onboarding`);
  for (let attempt = 0; attempt < 60 && status.status !== 200 && status.status !== 404; attempt++) {
    await new Promise((r) => setTimeout(r, 2000));
    status = await fetch(`${BASE_URL}/api/onboarding`).catch(() => status);
  }
  if (status.status === 404) return;
  const steps = (await status.json()) as { step: string; done: boolean }[];
  const pending = (step: string) => steps.some((entry) => entry.step === step && !entry.done);
  if (!pending('user')) throw new Error('Onboarding is partly done and has no user step left to run');

  const clientId = `${BASE_URL}/`;
  const post = async (path: string, body: unknown, token?: string) => {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status} ${await res.text()}`);
    return res;
  };

  const created = (await (
    await post('/api/onboarding/users', {
      client_id: clientId,
      name: 'Admin',
      username: USERNAME,
      password: PASSWORD,
      language: 'en',
    })
  ).json()) as { auth_code: string };

  const tokenRes = await fetch(`${BASE_URL}/auth/token`, {
    method: 'POST',
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code: created.auth_code,
      client_id: clientId,
    }),
  });
  if (!tokenRes.ok) throw new Error(`token exchange failed: ${tokenRes.status} ${await tokenRes.text()}`);
  const { access_token: token } = (await tokenRes.json()) as { access_token: string };

  for (const step of ['core_config', 'analytics']) {
    if (pending(step)) await post(`/api/onboarding/${step}`, {}, token);
  }
  if (pending('integration')) {
    await post(
      '/api/onboarding/integration',
      { client_id: clientId, redirect_uri: `${clientId}?auth_callback=1` },
      token,
    );
  }
}

export interface Tokens {
  access_token: string;
}

export function saveTokens(tokens: Tokens): void {
  writeFileSync(TOKEN_FILE, JSON.stringify(tokens, null, 2));
}

export function readTokens(): Tokens {
  if (!existsSync(TOKEN_FILE)) throw new Error('No token file - did global setup run?');
  return JSON.parse(readFileSync(TOKEN_FILE, 'utf8')) as Tokens;
}

/**
 * Sends one command over the websocket API and returns its result. Node ships a
 * WebSocket client, so this needs no dependency, and it is the same API the
 * frontend itself speaks.
 */
export async function callWebsocket<T = unknown>(message: Record<string, unknown>): Promise<T> {
  const token = readTokens().access_token;
  const socket = new WebSocket(`ws://127.0.0.1:${PORT}/api/websocket`);

  return new Promise<T>((resolve_, reject) => {
    const fail = (reason: string) => {
      socket.close();
      reject(new Error(reason));
    };
    const timer = setTimeout(() => fail('websocket timed out'), 30_000);

    socket.addEventListener('error', () => fail('websocket error'));
    socket.addEventListener('message', (event) => {
      const payload = JSON.parse(String(event.data)) as Record<string, unknown>;
      switch (payload.type) {
        case 'auth_required':
          socket.send(JSON.stringify({ type: 'auth', access_token: token }));
          return;
        case 'auth_invalid':
          clearTimeout(timer);
          fail('websocket authentication was refused');
          return;
        case 'auth_ok':
          socket.send(JSON.stringify({ id: 1, ...message }));
          return;
        case 'result': {
          clearTimeout(timer);
          socket.close();
          if (payload.success) resolve_(payload.result as T);
          else reject(new Error(`websocket command failed: ${JSON.stringify(payload.error)}`));
        }
      }
    });
  });
}

/** Puts a state on the bus, the way any client would. */
export async function setState(
  entityId: string,
  state: string,
  attributes: Record<string, unknown> = {},
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/states/${entityId}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${readTokens().access_token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ state, attributes }),
  });
  if (!res.ok) throw new Error(`setting ${entityId} failed: ${res.status} ${await res.text()}`);
}

export async function removeState(entityId: string): Promise<void> {
  await fetch(`${BASE_URL}/api/states/${entityId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${readTokens().access_token}` },
  });
}

/**
 * Gives the caller its own dashboard.
 *
 * Every spec file asks for a different name, so specs can run in parallel
 * without fighting over one dashboard - and none of them touches whatever the
 * manual test instance has on its own dashboards.
 */
export async function useDashboard(name: string, config: Record<string, unknown>): Promise<string> {
  const urlPath = `e2e-${name}`;
  const dashboards = await callWebsocket<{ url_path: string }[]>({
    type: 'lovelace/dashboards/list',
  });
  if (!dashboards.some((dashboard) => dashboard.url_path === urlPath)) {
    await callWebsocket({
      type: 'lovelace/dashboards/create',
      url_path: urlPath,
      title: `E2E ${name}`,
      mode: 'storage',
      show_in_sidebar: false,
    });
  }
  await callWebsocket({ type: 'lovelace/config/save', url_path: urlPath, config });
  return urlPath;
}

/**
 * Waits until the core has finished starting.
 *
 * `/manifest.json` answers well before that, and the card resource is
 * registered from an EVENT_HOMEASSISTANT_STARTED listener - so a suite that
 * only waited for HTTP would read the resource store mid-startup and see
 * whatever was left there by the previous run.
 */
export async function waitForCoreRunning(timeoutMs = 180_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const config = await callWebsocket<{ state: string }>({ type: 'get_config' }).catch(() => undefined);
    if (config?.state === 'RUNNING') return;
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`Home Assistant did not reach state RUNNING within ${timeoutMs}ms`);
}

/** The Lovelace resources Home Assistant has persisted. */
export async function resources(): Promise<{ id: string; url: string }[]> {
  return callWebsocket({ type: 'lovelace/resources' });
}

interface FlowStep {
  type: 'form' | 'create_entry' | 'abort';
  flow_id: string;
  step_id?: string;
  reason?: string;
  data_schema?: { name: string; selector?: { select?: { options: (string | { value: string })[] } } }[];
}

async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: init.method ?? (init.body === undefined ? 'GET' : 'POST'),
    headers: { Authorization: `Bearer ${readTokens().access_token}`, 'Content-Type': 'application/json' },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as T;
}

/**
 * Makes sure the integration has at least one config entry.
 *
 * Home Assistant only sets an integration up when it has an entry, and the
 * bundled card is registered as a Lovelace resource from that setup. The entry
 * is created through the real config flow. Its first step reads the location
 * list from seatemperatures.net, so this needs outbound network access.
 */
export async function ensureConfigEntry(): Promise<void> {
  const entries = await api<{ domain: string }[]>('/api/config/config_entries/entry?domain=seatemperatures');
  if (entries.length > 0) return;

  const optionFor = (step: FlowStep, field: string, preferred: string): string => {
    const options = step.data_schema?.find((entry) => entry.name === field)?.selector?.select?.options ?? [];
    const values = options.map((option) => (typeof option === 'string' ? option : option.value));
    const choice = values.includes(preferred) ? preferred : values[0];
    if (!choice) {
      throw new Error(
        `The config flow offered no ${field} options (step ${step.step_id}) - seatemperatures.net unreachable?`,
      );
    }
    return choice;
  };

  let step = await api<FlowStep>('/api/config/config_entries/flow', {
    body: { handler: 'seatemperatures', show_advanced_options: false },
  });
  const wanted: Record<string, [string, string]> = {
    user: ['continent', 'Europe'],
    country: ['country', 'Germany'],
    place: ['place', 'Lindau'],
  };
  for (let guard = 0; step.type === 'form' && guard < 5; guard++) {
    const [field, preferred] = wanted[step.step_id ?? ''] ?? [];
    if (!field) throw new Error(`Unexpected config flow step: ${step.step_id}`);
    step = await api<FlowStep>(`/api/config/config_entries/flow/${step.flow_id}`, {
      body: { [field]: optionFor(step, field, preferred) },
    });
  }
  if (step.type !== 'create_entry') throw new Error(`Config flow ended with ${step.type} ${step.reason ?? ''}`);
}

/** Waits for the integration to have registered its Lovelace resource. */
export async function waitForCardResource(timeoutMs = 120_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const found = (await resources()).some((resource) => resource.url.startsWith('/seatemperatures_frontend/'));
    if (found) return;
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`The card resource was not registered within ${timeoutMs}ms`);
}

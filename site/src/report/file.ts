// Filing a report: the server side of the report form, run by the Pages Function in
// site/functions/api/report.ts. Kept free of Cloudflare's types so it can be tested with Node.

import { Invalid, issueFor, parseReport } from "./report.ts";

export interface Env {
  /** A fine-grained GitHub token with read and write access to issues on GITHUB_REPO only. */
  GITHUB_TOKEN?: string;
  /** Where issues are filed, as ``owner/name``. */
  GITHUB_REPO?: string;
  /** Turnstile's secret key: every report must carry a token from the widget. */
  TURNSTILE_SECRET_KEY?: string;
}

type Fetch = typeof fetch;

const MAX_BYTES = 32_000;

export async function fileReport(request: Request, env: Env, fetcher: Fetch = fetch): Promise<Response> {
  if (!env.GITHUB_TOKEN || !env.GITHUB_REPO || !env.TURNSTILE_SECRET_KEY) {
    console.error("report: GITHUB_TOKEN, GITHUB_REPO and TURNSTILE_SECRET_KEY must all be set");
    return reply(503, { error: "Reports can't be sent right now." });
  }

  const raw = await request.text();
  if (raw.length > MAX_BYTES) return reply(413, { error: "That report is too long." });
  let payload: { report?: unknown; turnstile?: unknown };
  try {
    payload = JSON.parse(raw);
  } catch {
    return reply(400, { error: "That report could not be read." });
  }

  const human = await verifyTurnstile(
    fetcher,
    env.TURNSTILE_SECRET_KEY,
    typeof payload.turnstile === "string" ? payload.turnstile : "",
    request.headers.get("CF-Connecting-IP"),
  );
  if (!human) return reply(403, { error: "The check that you're not a bot failed. Please try again." });

  let issue;
  try {
    issue = issueFor(parseReport(payload.report), new URL(request.url).origin);
  } catch (error) {
    if (error instanceof Invalid) return reply(422, { error: `Please check the form: ${error.message}.` });
    throw error;
  }

  const response = await fetcher(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "splits-report-form",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify(issue),
  });
  if (!response.ok) {
    console.error(`report: GitHub answered ${response.status}: ${await response.text()}`);
    return reply(502, { error: "The report couldn't be filed. Please try again later." });
  }
  const created = (await response.json()) as { number: number; html_url: string };
  return reply(201, { number: created.number, url: created.html_url });
}

async function verifyTurnstile(fetcher: Fetch, secret: string, token: string, ip: string | null): Promise<boolean> {
  if (!token) return false;
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token);
  if (ip) form.append("remoteip", ip);
  const response = await fetcher("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    body: form,
  });
  if (!response.ok) return false;
  const outcome = (await response.json()) as { success?: boolean };
  return outcome.success === true;
}

function reply(status: number, body: object): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

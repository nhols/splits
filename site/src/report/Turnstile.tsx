// Cloudflare Turnstile: the check that a report comes from a person. Its script is loaded only
// when the form is shown. Without VITE_TURNSTILE_SITE_KEY (local development) it renders nothing.

import { useEffect, useRef } from "react";

interface TurnstileApi {
  render(element: HTMLElement, options: Record<string, unknown>): string;
  reset(widget: string): void;
  remove(widget: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;
const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

let loading: Promise<TurnstileApi> | null = null;

function load(): Promise<TurnstileApi> {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("Turnstile did not load")));
    script.onerror = () => {
      loading = null;
      reject(new Error("Turnstile did not load"));
    };
    document.head.appendChild(script);
  });
  return loading;
}

/** The widget. ``onToken`` gets a token when the check passes, and null when it expires.
 * Changing ``generation`` resets the widget: a token can be used only once. */
export function Turnstile({ onToken, generation }: { onToken: (token: string | null) => void; generation: number }) {
  const element = useRef<HTMLDivElement>(null);
  const widget = useRef<string | null>(null);
  const callback = useRef(onToken);
  callback.current = onToken;

  useEffect(() => {
    if (!SITE_KEY) return;
    let cancelled = false;
    load()
      .then((turnstile) => {
        if (cancelled || !element.current) return;
        widget.current = turnstile.render(element.current, {
          sitekey: SITE_KEY,
          size: "flexible",
          theme: document.documentElement.dataset.theme === "dark" ? "dark" : "light",
          callback: (token: string) => callback.current(token),
          "expired-callback": () => callback.current(null),
          "error-callback": () => callback.current(null),
        });
      })
      .catch(() => callback.current(null));
    return () => {
      cancelled = true;
      if (widget.current) window.turnstile?.remove(widget.current);
      widget.current = null;
    };
  }, []);

  useEffect(() => {
    if (generation > 0 && widget.current) {
      callback.current(null);
      window.turnstile?.reset(widget.current);
    }
  }, [generation]);

  return SITE_KEY ? <div ref={element} className="turnstile" /> : null;
}

export const turnstileEnabled = Boolean(SITE_KEY);

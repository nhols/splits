interface ImportMetaEnv {
  /** Where the table exports and the database are downloaded from (default: data/downloads/). */
  readonly VITE_DOWNLOADS_URL?: string;
  /** Cloudflare Turnstile's site key for the report form (unset: no check is shown). */
  readonly VITE_TURNSTILE_SITE_KEY?: string;
}

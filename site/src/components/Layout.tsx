import { useEffect, useState, type ReactNode } from "react";
import { useIndex } from "../data/load";
import { date } from "../data/format";
import { Link, useLocation } from "../router";
import { Search } from "./Search";
import "./layout.css";

const NAV = [
  { to: "/events", label: "Events" },
  { to: "/races", label: "Races" },
  { to: "/athletes", label: "Athletes" },
  { to: "/compare", label: "Compare" },
  { to: "/data", label: "Data" },
];

export function Layout({ children }: { children: ReactNode }) {
  const { path, params } = useLocation();
  const index = useIndex();
  const here = path + (params.size ? `?${params}` : "");
  const report = path === "/report" ? here : `/report?from=${encodeURIComponent(here)}`;
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand" aria-label="Splits home">
            <Logo />
            <span>Splits</span>
          </Link>
          <nav className="nav" aria-label="Main">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={path === item.to || path.startsWith(item.to + "/") ? "active" : ""}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="topbar-tools">
            <Search />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main>{children}</main>
      <footer className="footer">
        <div className="footer-inner">
          <p className="muted">
            From official documents by World Athletics, OMEGA and the Olympic Games ·{" "}
            <Link to="/data" className="link">Data</Link> ·{" "}
            <Link to={report} className="link">Report a problem or a missing race</Link> · built{" "}
            {date(index.build.builtAt.slice(0, 10))}
          </p>
        </div>
      </footer>
    </div>
  );
}

function Logo() {
  // The track, as in the favicon (public/favicon.svg), cropped to the oval.
  return (
    <svg width="30" height="22" viewBox="1 5 30 22" aria-hidden="true">
      <rect x="1" y="5" width="30" height="22" rx="11" fill="#d4472c" />
      <rect
        x="4.25"
        y="8.25"
        width="23.5"
        height="15.5"
        rx="7.75"
        fill="none"
        stroke="#fff"
        strokeWidth="1"
        strokeOpacity="0.85"
      />
      <rect x="7.5" y="11.5" width="17" height="9" rx="4.5" fill="#4a9d55" stroke="#fff" strokeWidth="0.9" />
    </svg>
  );
}

type Theme = "light" | "dark";

function storedTheme(): Theme | null {
  try {
    const value = window.localStorage.getItem("theme");
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme as Theme | undefined) ?? "light",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => {
      if (!storedTheme()) setTheme(media.matches ? "dark" : "light");
    };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      window.localStorage.setItem("theme", next);
    } catch {
      // Storage may be unavailable; the choice then lasts for this visit only.
    }
  };
  return (
    <button type="button" className="icon-button" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
      {theme === "dark" ? (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4.5" fill="currentColor" />
          {Array.from({ length: 8 }, (_, i) => (
            <path key={i} d="M12 2.5v2.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" transform={`rotate(${i * 45} 12 12)`} />
          ))}
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" fill="currentColor" />
        </svg>
      )}
    </button>
  );
}

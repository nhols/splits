// The About page's sections, to jump between: a list beside the text on a wide screen, a row of
// buttons under the site header on a narrow one, the section being read marked in either.

import { useEffect, useLayoutEffect, useRef, useState } from "react";

export interface Section {
  id: string;
  title: string;
}

/** Below this width the list becomes a row under the header (as in about.css). */
const NARROW = 1000;

/** How far down the window a section must reach to count as the one being read. */
function offset(nav: HTMLElement | null): number {
  const topbar = document.querySelector<HTMLElement>(".topbar")?.offsetHeight ?? 60;
  const row = nav && window.innerWidth < NARROW ? nav.offsetHeight : 0;
  return topbar + row + 16;
}

export function AboutNav({ sections }: { sections: readonly Section[] }) {
  const nav = useRef<HTMLElement>(null);
  const [current, setCurrent] = useState(sections[0]?.id ?? "");

  // Headings stop below the header (and the row, on a narrow screen) when jumped to.
  useLayoutEffect(() => {
    const place = () => {
      const topbar = document.querySelector<HTMLElement>(".topbar")?.offsetHeight ?? 60;
      document.documentElement.style.setProperty("--topbar-height", `${topbar}px`);
      document.documentElement.style.setProperty("--about-offset", `${offset(nav.current)}px`);
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, []);

  // The section being read: the last whose heading has reached the top of the window, or the
  // last of all once the page is scrolled to its end. A handful of headings, so it is read on
  // every scroll.
  useEffect(() => {
    const update = () => {
      const line = offset(nav.current) + 8;
      const atEnd = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      let reached = sections[0]?.id ?? "";
      for (const { id } of sections) {
        const heading = document.getElementById(id);
        if (heading && heading.getBoundingClientRect().top <= line) reached = id;
      }
      setCurrent(atEnd ? sections[sections.length - 1]!.id : reached);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [sections]);

  // On a narrow screen, keep the current section's button in view along the row.
  useEffect(() => {
    const list = nav.current?.querySelector("ol");
    const link = nav.current?.querySelector<HTMLElement>(`a[href="#${current}"]`);
    if (!list || !link || window.innerWidth >= NARROW) return;
    list.scrollTo({ left: link.offsetLeft - 16, behavior: "smooth" });
  }, [current]);

  // A link to a section, opened from elsewhere, lands on it.
  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (id && document.getElementById(id)) requestAnimationFrame(() => jump(id, "auto"));
  }, []);

  const jump = (id: string, behavior: ScrollBehavior = "smooth") => {
    const heading = document.getElementById(id);
    if (!heading) return;
    const top = heading.getBoundingClientRect().top + window.scrollY - offset(nav.current) + 4;
    window.scrollTo({ top, behavior });
    window.history.replaceState(window.history.state, "", `#${id}`);
    setCurrent(id);
  };

  return (
    <nav ref={nav} className="about-nav" aria-label="On this page">
      <span className="about-nav-title">On this page</span>
      <ol>
        {sections.map(({ id, title }) => (
          <li key={id}>
            <a
              href={`#${id}`}
              className={current === id ? "on" : undefined}
              aria-current={current === id ? "location" : undefined}
              onClick={(event) => {
                event.preventDefault();
                jump(id);
              }}
            >
              {title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

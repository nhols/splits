import { EventList } from "../components/EventList";
import "./home.css";
import "./pages.css";

export function EventsPage() {
  return (
    <div className="page stack" style={{ "--gap": "24px" } as React.CSSProperties}>
      <header className="page-header">
        <h1>Events</h1>
      </header>
      <EventList />
    </div>
  );
}

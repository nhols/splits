import { Component, Suspense, type ReactNode } from "react";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { AthletePage } from "./pages/AthletePage";
import { AthletesPage } from "./pages/AthletesPage";
import { ComparePage } from "./pages/ComparePage";
import { DataPage } from "./pages/DataPage";
import { EventPage } from "./pages/EventPage";
import { EventsPage } from "./pages/EventsPage";
import { HomePage } from "./pages/HomePage";
import { NotFound } from "./pages/NotFound";
import { RacePage } from "./pages/RacePage";
import { RacesPage } from "./pages/RacesPage";
import { ReportPage } from "./pages/ReportPage";
import { match, RouterProvider, useLocation } from "./router";

function Routes() {
  const { path, params: query } = useLocation();
  let params: Record<string, string> | null;
  if (path === "/") return <HomePage />;
  if (path === "/events") return <EventsPage />;
  if ((params = match("/events/:event", path))) return <EventPage key={params.event} event={params.event!} />;
  if (path === "/races") return <RacesPage />;
  if ((params = match("/races/*", path))) return <RacePage key={params.rest} id={params.rest!} />;
  if (path === "/athletes") return <AthletesPage />;
  if ((params = match("/athletes/:id", path))) return <AthletePage key={params.id} id={params.id!} />;
  if (path === "/compare") return <ComparePage />;
  if (path === "/data") return <DataPage />;
  if (path === "/report") return <ReportPage key={query.get("from") ?? ""} />;
  return <NotFound />;
}

class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidUpdate(previous: { resetKey: string }) {
    if (previous.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }
  render() {
    if (this.state.error) {
      return (
        <div className="page">
          <h1>Something went wrong</h1>
          <p className="lede" style={{ marginTop: 12 }}>
            {this.state.error.message}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

function Page() {
  const { path } = useLocation();
  return (
    <ErrorBoundary resetKey={path}>
      <Suspense fallback={<div className="page"><Loading /></div>}>
        <Routes />
      </Suspense>
    </ErrorBoundary>
  );
}

export function App() {
  return (
    <RouterProvider>
      <ErrorBoundary resetKey="app">
        <Suspense fallback={<div className="page"><Loading label="Loading the dataset" /></div>}>
          <Layout>
            <Page />
          </Layout>
        </Suspense>
      </ErrorBoundary>
    </RouterProvider>
  );
}

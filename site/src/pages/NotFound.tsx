import { Link } from "../router";

export function NotFound() {
  return (
    <div className="page stack">
      <h1>Not found</h1>
      <p className="lede">
        There is nothing here. Try the <Link to="/" className="link">home page</Link> or search with ⌘K.
      </p>
    </div>
  );
}

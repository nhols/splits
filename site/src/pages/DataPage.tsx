// The data: what is in it, where it comes from, how it is checked, and the whole of it to
// download.

import { Card } from "../components/ui";
import { count, dateRange } from "../data/format";
import { dataUrl, useIndex } from "../data/load";
import { Link } from "../router";
import "./pages.css";
import "./data.css";

export function DataPage() {
  const index = useIndex();
  return (
    <div className="page stack" style={{ "--gap": "28px" } as React.CSSProperties}>
      <header className="page-header">
        <h1>Data</h1>
        <p className="lede">Every split is read from an official race document, linked from its race.</p>
      </header>

      <div className="kpis kpis-5">
        <Stat label="Races" value={count(index.build.races)} />
        <Stat label="Performances" value={count(index.build.performances)} />
        <Stat label="Athletes" value={count(index.build.athletes)} />
        <Stat label="Splits" value={count(index.build.splits)} />
        <Stat label="Documents" value={count(index.build.documents)} />
      </div>

      <Card
        title="Download"
        actions={
          <a className="button primary" href={dataUrl("downloads/splits.duckdb")} download>
            DuckDB
          </a>
        }
      >
        <div className="table-wrap">
          <table className="data">
            <tbody>
              {index.tables.map((t) => (
                <tr key={t.name}>
                  <td className="mono">{t.name}</td>
                  <td className="right">{count(t.rows)} rows</td>
                  <td className="right">
                    <a className="link" href={dataUrl(`downloads/${t.name}.csv`)} download>
                      CSV
                    </a>{" "}
                    ·{" "}
                    <a className="link" href={dataUrl(`downloads/${t.name}.parquet`)} download>
                      Parquet
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid-2 align-start">
        <Card title="Competitions">
          <div className="table-wrap">
            <table className="data">
              <tbody>
                {index.competitions.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link to={`/races?competition=${c.id}`} className="link-plain">
                        {c.name}
                      </Link>
                    </td>
                    <td className="secondary">{dateRange(c.startDate, c.endDate)}</td>
                    <td className="right">{c.documents} documents</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="stack" style={{ "--gap": "24px" } as React.CSSProperties}>
          <Card title="Documents">
            <table className="data">
              <tbody>
                {index.formats.map((f) => (
                  <tr key={f.id}>
                    <td>{f.name}</td>
                    <td className="right">{f.documents}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card title="Checks">
            <table className="data">
              <tbody>
                {index.checks.map((c) => (
                  <tr key={c.id}>
                    <td title={c.explanation}>{c.title}</td>
                    <td className="right">{c.flags || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

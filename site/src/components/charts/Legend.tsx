interface Item {
  id: string;
  label: string;
  color: string;
}

/** A legend whose items highlight their series on hover or focus. Keys mirror the marks:
 * a short line for lines, a dot for dots. */
export function Legend({
  items,
  shape = "line",
  highlight,
  onHighlight,
}: {
  items: Item[];
  shape?: "line" | "dot";
  highlight?: string | null;
  onHighlight?: (id: string | null) => void;
}) {
  return (
    <div className="legend">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`legend-item${highlight && highlight !== item.id ? " faded" : ""}`}
          onPointerEnter={() => onHighlight?.(item.id)}
          onPointerLeave={() => onHighlight?.(null)}
          onFocus={() => onHighlight?.(item.id)}
          onBlur={() => onHighlight?.(null)}
        >
          <span
            className={shape === "line" ? "chart-key" : "legend-swatch-dot"}
            style={{ background: item.color }}
          />
          {item.label}
        </button>
      ))}
    </div>
  );
}

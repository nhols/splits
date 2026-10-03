// A mark printed beside a result (PB, TR16.8, YC). Pointing at it, or tapping it, shows what it
// means just above it, over the page, so nothing moves.

import { useMemo } from "react";
import { useIndex } from "../data/load";
import { Explained } from "./Explained";

export function Tag({ value }: { value: string }) {
  const index = useIndex();
  const meanings = useMemo(() => new Map(index.annotations.map((a) => [a.value, a.meaning])), [index]);
  const meaning = meanings.get(value);
  return meaning ? <ExplainedTag value={value} meaning={meaning} /> : <span className="tag">{value}</span>;
}

function ExplainedTag({ value, meaning }: { value: string; meaning: string }) {
  return (
    <Explained className="tag tag-button" explanation={meaning}>
      {value}
    </Explained>
  );
}

export type FlowItem = { record_id?: string; label?: string; href?: string; amount?: number; source?: string };
export type FlowColumn = {
  key: string;
  label: string;
  count: number;
  color?: string;
  items?: FlowItem[];
  result?: string;
  doctors?: number | null;
};
export type ResolutionFlowData = {
  sources: FlowColumn[];
  outcomes: FlowColumn[];
  results: FlowColumn[];
  bands: Array<{ from: string; to: string; count: number }>;
  doctor_count: number;
  row_count: number;
};

export function ResolutionFlow({
  flow,
  onOpen,
}: {
  flow: ResolutionFlowData;
  onOpen: (title: string, items: FlowItem[]) => void;
}) {
  const sources = flow.sources || [];
  const outcomes = flow.outcomes || [];
  const results = flow.results || [];
  const total = Math.max(1, sources.reduce((sum, row) => sum + row.count, 0));
  const H = 330;
  const top = 24;
  const gap = 10;
  const w = 14;
  const xL = 150;
  const xM = 470;
  const xR = 790;
  const sc = (H - top * 2 - gap * (Math.max(sources.length, outcomes.length, 1) - 1)) / total;
  const place = (items: FlowColumn[]) => {
    const used = items.reduce((sum, item) => sum + item.count, 0) * sc + gap * Math.max(0, items.length - 1);
    let y = top + Math.max(0, (H - top * 2 - used) / 2);
    const out: Record<string, number> = {};
    items.forEach((item) => {
      out[item.key] = y;
      y += Math.max(item.count, 0) * sc + gap;
    });
    return out;
  };
  const yL = place(sources);
  const yM = place(outcomes);
  const yR = place(results);
  const offL = { ...yL };
  const offMi = { ...yM };
  const offMo = { ...yM };
  const offR = { ...yR };
  const band = (x1: number, y1: number, x2: number, y2: number, h: number, col: string) => {
    const mx = (x1 + x2) / 2;
    return `M${x1} ${y1} C${mx} ${y1},${mx} ${y2},${x2} ${y2} L${x2} ${y2 + h} C${mx} ${y2 + h},${mx} ${y1 + h},${x1} ${y1 + h} Z`;
  };
  const paths: Array<{ d: string; color: string }> = [];
  sources.forEach((source) => {
    outcomes.forEach((outcome) => {
      const count = (flow.bands || []).find((row) => row.from === source.key && row.to === outcome.key)?.count || 0;
      if (!count) return;
      const h = count * sc;
      paths.push({
        d: band(xL + w, offL[source.key], xM, offMi[outcome.key], h, outcome.color || '#8a9bb0'),
        color: outcome.color || '#8a9bb0',
      });
      offL[source.key] += h;
      offMi[outcome.key] += h;
    });
  });
  results.forEach((result) => {
    outcomes
      .filter((outcome) => outcome.result === result.key)
      .forEach((outcome) => {
        const h = outcome.count * sc;
        paths.push({
          d: band(xM + w, offMo[outcome.key], xR, offR[result.key], h, outcome.color || '#8a9bb0'),
          color: outcome.color || '#8a9bb0',
        });
        offMo[outcome.key] += h;
        offR[result.key] += h;
      });
  });

  return (
    <div className="sankey" data-tour="sankey">
      <svg viewBox={`0 0 1000 ${H}`} role="img" aria-label={`Records flow from ${sources.length} sources to ${flow.doctor_count} golden doctors`}>
        <text className="s" x={xL - 8} y={12} textAnchor="end">
          SOURCES
        </text>
        <text className="s" x={xM} y={12}>
          HOW IT WAS RESOLVED
        </text>
        <text className="s" x={xR} y={12}>
          RESULT
        </text>
        {paths.map((path) => (
          <path key={path.d} className="band" fill={path.color} d={path.d} />
        ))}
        {sources.map((source) => {
          const h = Math.max(source.count * sc, 2);
          return (
            <g key={source.key} className="snode" onClick={() => onOpen(source.label, source.items || [])}>
              <rect x={xL} y={yL[source.key]} width={w} height={h} rx={3} fill="#5f7896" />
              <text x={xL - 8} y={yL[source.key] + h / 2 + 4} textAnchor="end">
                {source.label} <tspan className="s">{source.count}</tspan>
              </text>
            </g>
          );
        })}
        {outcomes.map((outcome) => {
          const h = Math.max(outcome.count * sc, 2);
          return (
            <g key={outcome.key} className="snode" onClick={() => onOpen(outcome.label, outcome.items || [])}>
              <rect x={xM} y={yM[outcome.key]} width={w} height={h} rx={3} fill={outcome.color || '#8a9bb0'} />
              <text className="halo" x={xM + w + 8} y={yM[outcome.key] + h / 2 + 4}>
                {outcome.label} · <tspan fontWeight={600}>{outcome.count}</tspan>
              </text>
            </g>
          );
        })}
        {results.map((result) => {
          const h = Math.max(result.count * sc, 2);
          const title = result.key === 'gold' ? `${result.doctors ?? flow.doctor_count} golden doctors` : result.label;
          return (
            <g key={result.key} className="snode" onClick={() => onOpen(title, result.items || [])}>
              <rect x={xR} y={yR[result.key]} width={w} height={h} rx={3} fill={result.color || '#1e5aa8'} />
              <text x={xR + w + 10} y={yR[result.key] + h / 2 - 3} fontWeight={600}>
                {title}
              </text>
              <text className="s" x={xR + w + 10} y={yR[result.key] + h / 2 + 13}>
                {result.count} records
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

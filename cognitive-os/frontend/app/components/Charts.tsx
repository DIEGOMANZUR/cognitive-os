"use client";

import { useId, useMemo, useState } from "react";

/**
 * Lightweight SVG chart primitives — no chart library, no canvas. The console
 * needs at-a-glance trend and proportion visualisations, not a full BI tool,
 * so we keep the surface small, themable via `currentColor` + design tokens,
 * and accessible (each chart pairs visuals with text values + ARIA labels).
 */

function buildPath(points: Array<[number, number]>): string {
  if (points.length === 0) return "";
  return points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`)
    .join(" ");
}

function smoothPath(points: Array<[number, number]>): string {
  if (points.length < 2) return buildPath(points);
  const parts: string[] = [`M${points[0][0]} ${points[0][1]}`];
  for (let i = 1; i < points.length; i += 1) {
    const [x, y] = points[i];
    const [px, py] = points[i - 1];
    const cx = (px + x) / 2;
    parts.push(`Q ${px} ${py} ${cx} ${(py + y) / 2}`);
    parts.push(`T ${x} ${y}`);
  }
  return parts.join(" ");
}

/** Inline sparkline used inside metric cards. */
export function Sparkline({
  data,
  width = 120,
  height = 32,
  stroke = "var(--accent)",
  fill = "var(--accent-soft)",
  label
}: {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  label?: string;
}) {
  if (data.length < 2) {
    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        className="spark"
        role="img"
        aria-label={label ?? "tendencia sin datos suficientes"}
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="var(--line)"
          strokeDasharray="3 4"
        />
      </svg>
    );
  }

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const points = data.map<[number, number]>((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return [x, y];
  });
  const linePath = smoothPath(points);
  const areaPath = `${linePath} L ${width} ${height} L 0 ${height} Z`;
  const lastY = points[points.length - 1][1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className="spark"
      role="img"
      aria-label={label ?? `tendencia, último valor ${data[data.length - 1]}`}
    >
      <path d={areaPath} fill={fill} stroke="none" />
      <path
        d={linePath}
        fill="none"
        stroke={stroke}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={width} cy={lastY} r={2.6} fill={stroke} />
    </svg>
  );
}

/** Multi-series area chart for the dashboard. */
export function AreaChart({
  series,
  height = 180,
  yLabel,
  formatter = (v) => v.toFixed(0)
}: {
  series: Array<{ name: string; data: number[]; color?: string }>;
  height?: number;
  yLabel?: string;
  formatter?: (value: number) => string;
}) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);

  const stats = useMemo(() => {
    let max = -Infinity;
    let min = Infinity;
    let length = 0;
    for (const s of series) {
      length = Math.max(length, s.data.length);
      for (const v of s.data) {
        if (v > max) max = v;
        if (v < min) min = v;
      }
    }
    if (!isFinite(max)) {
      max = 1;
      min = 0;
    }
    if (min === max) {
      min = min - 1;
      max = max + 1;
    }
    return { max, min, length };
  }, [series]);

  if (stats.length < 2) {
    return (
      <div className="empty-state" style={{ padding: "22px 12px" }}>
        <span className="empty-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M3 3v18h18" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" />
          </svg>
        </span>
        <span className="empty-msg">Aún no hay datos suficientes para graficar.</span>
      </div>
    );
  }

  const padding = { top: 12, right: 14, bottom: 22, left: 38 };
  const width = 640;
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;
  const stepX = innerW / (stats.length - 1);
  const yRange = stats.max - stats.min;

  const yToPx = (v: number) =>
    padding.top + innerH - ((v - stats.min) / yRange) * innerH;
  const iToPx = (i: number) => padding.left + i * stepX;

  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) =>
    stats.min + ((stats.max - stats.min) * i) / ticks
  );

  const COLORS = ["var(--accent)", "var(--iris)", "var(--warn)", "var(--danger)"];

  return (
    <div style={{ position: "relative" }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        className="chart"
        role="img"
        aria-label={`Gráfico de área${yLabel ? ` · ${yLabel}` : ""}`}
        preserveAspectRatio="none"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / rect.width) * width;
          const ratio = (x - padding.left) / innerW;
          const idx = Math.round(ratio * (stats.length - 1));
          setHover(Math.max(0, Math.min(stats.length - 1, idx)));
        }}
      >
        {yTicks.map((tickValue, i) => {
          const y = yToPx(tickValue);
          return (
            <g key={`y-${i}`}>
              <line
                className="chart-grid"
                x1={padding.left}
                x2={width - padding.right}
                y1={y}
                y2={y}
                strokeDasharray="2 4"
              />
              <text className="chart-axis" x={padding.left - 8} y={y + 3} textAnchor="end">
                {formatter(tickValue)}
              </text>
            </g>
          );
        })}

        {series.map((s, sIdx) => {
          const color = s.color ?? COLORS[sIdx % COLORS.length];
          const points = s.data.map<[number, number]>((v, i) => [iToPx(i), yToPx(v)]);
          if (points.length < 2) return null;
          const linePath = smoothPath(points);
          const areaPath = `${linePath} L ${iToPx(s.data.length - 1)} ${padding.top + innerH} L ${padding.left} ${padding.top + innerH} Z`;
          const gradientId = `grad-${id}-${sIdx}`;
          return (
            <g key={s.name}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <path d={areaPath} fill={`url(#${gradientId})`} />
              <path
                d={linePath}
                fill="none"
                stroke={color}
                strokeWidth={1.8}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {hover !== null && (
                <circle
                  cx={iToPx(hover)}
                  cy={yToPx(s.data[hover] ?? stats.min)}
                  r={3.4}
                  fill={color}
                  stroke="var(--bg-deep)"
                  strokeWidth={1.4}
                />
              )}
            </g>
          );
        })}

        {hover !== null && (
          <line
            x1={iToPx(hover)}
            x2={iToPx(hover)}
            y1={padding.top}
            y2={padding.top + innerH}
            stroke="var(--glass-border-hi)"
            strokeDasharray="2 3"
          />
        )}
      </svg>

      <div className="chart-legend" style={{ marginTop: 6 }}>
        {series.map((s, sIdx) => (
          <span key={s.name}>
            <span
              className="legend-swatch"
              style={{ background: s.color ?? COLORS[sIdx % COLORS.length] }}
            />
            {s.name}
            {hover !== null && (
              <span className="muted" style={{ marginLeft: 4 }}>
                · {formatter(s.data[hover] ?? 0)}
              </span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Compact horizontal bar comparison — for tool scorecards, status counts, etc. */
export function BarList({
  items,
  formatter = (v) => v.toString(),
  max
}: {
  items: Array<{ label: string; value: number; tone?: "ok" | "warn" | "danger" | "info" }>;
  formatter?: (value: number) => string;
  max?: number;
}) {
  const peak = max ?? Math.max(1, ...items.map((it) => it.value));
  return (
    <div className="stack" style={{ gap: 9 }}>
      {items.map((item) => {
        const pct = Math.min(100, Math.round((item.value / peak) * 100));
        const tone = item.tone ?? "info";
        const color =
          tone === "ok"
            ? "var(--ok)"
            : tone === "warn"
              ? "var(--warn)"
              : tone === "danger"
                ? "var(--danger)"
                : "var(--accent)";
        return (
          <div key={item.label} className="stack" style={{ gap: 4 }}>
            <div className="spread small">
              <span className="ellipsis" style={{ maxWidth: "70%" }}>
                {item.label}
              </span>
              <span className="mono faint">{formatter(item.value)}</span>
            </div>
            <div className="bar" style={{ height: 5 }}>
              <span
                style={{
                  width: `${pct}%`,
                  background: `linear-gradient(90deg, ${color}, ${color}aa)`
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Donut chart for proportions (e.g. job status mix). */
export function Donut({
  slices,
  size = 140,
  thickness = 18,
  label,
  centerValue,
  centerSub
}: {
  slices: Array<{ name: string; value: number; color?: string }>;
  size?: number;
  thickness?: number;
  label?: string;
  centerValue?: string;
  centerSub?: string;
}) {
  const total = slices.reduce((s, v) => s + v.value, 0);
  const radius = size / 2 - thickness / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const COLORS = ["var(--accent)", "var(--iris)", "var(--warn)", "var(--danger)", "var(--info)"];

  return (
    <div className="row" style={{ gap: 14, alignItems: "center" }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={label ?? "proporciones"}
      >
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="var(--bg-deep)"
          strokeWidth={thickness}
        />
        {total > 0 &&
          slices.map((slice, i) => {
            const fraction = slice.value / total;
            const dash = circumference * fraction;
            const gap = circumference - dash;
            const color = slice.color ?? COLORS[i % COLORS.length];
            const node = (
              <circle
                key={slice.name}
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke={color}
                strokeWidth={thickness}
                strokeDasharray={`${dash} ${gap}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
                transform={`rotate(-90 ${cx} ${cy})`}
              />
            );
            offset += dash;
            return node;
          })}
        {centerValue && (
          <text
            x={cx}
            y={cy - 4}
            textAnchor="middle"
            fill="var(--text)"
            fontFamily="var(--mono)"
            fontSize={18}
            fontWeight={700}
          >
            {centerValue}
          </text>
        )}
        {centerSub && (
          <text
            x={cx}
            y={cy + 14}
            textAnchor="middle"
            fill="var(--text-faint)"
            fontSize={10}
            style={{ textTransform: "uppercase", letterSpacing: 0.6 }}
          >
            {centerSub}
          </text>
        )}
      </svg>
      <div className="chart-legend" style={{ flexDirection: "column", gap: 6, alignItems: "flex-start" }}>
        {slices.map((slice, i) => (
          <span key={slice.name}>
            <span
              className="legend-swatch"
              style={{ background: slice.color ?? COLORS[i % COLORS.length] }}
            />
            {slice.name}
            <span className="muted" style={{ marginLeft: 6 }}>
              {slice.value}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

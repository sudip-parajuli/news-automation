import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';

interface ChartDataPoint {
  label: string;
  value: number;
  unit?: string;
}

interface ChartData {
  type: "bar" | "line";
  title: string;
  data: ChartDataPoint[];
}

export const ChartCard: React.FC<{
  chartData: ChartData;
  durationInFrames: number;
}> = ({ chartData, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 120, mass: 1 },
    durationInFrames: 25,
  });

  const maxValue = Math.max(...chartData.data.map(d => d.value), 1);
  const chartWidth = 1400;
  const chartHeight = 400;
  const padding = { top: 60, right: 40, bottom: 100, left: 100 };
  const barWidth = Math.min(80, (chartWidth - padding.left - padding.right) / chartData.data.length * 0.6);
  const gap = (chartWidth - padding.left - padding.right - barWidth * chartData.data.length) / (chartData.data.length + 1);

  const bars = chartData.data.map((point, i) => {
    const barHeight = (point.value / maxValue) * (chartHeight - padding.top - padding.bottom);
    const x = padding.left + gap + i * (barWidth + gap);
    const y = chartHeight - padding.bottom - barHeight;
    return { x, y, width: barWidth, height: barHeight, point, index: i };
  });

  const pathD = bars.map((bar, i) => {
    const x = bar.x + bar.width / 2;
    const y = bar.y;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  const areaD = `${pathD} L ${bars[bars.length - 1].x + bars[bars.length - 1].width / 2} ${chartHeight - padding.bottom} L ${bars[0].x + bars[0].width / 2} ${chartHeight - padding.bottom} Z`;

  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: '80px' }}>
      <div
        style={{
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          borderRadius: '20px',
          padding: '24px 32px 16px',
          maxWidth: '90%',
          transform: `translateY(${(1 - entrance) * 60}px) scale(${entrance})`,
          opacity: entrance,
          boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '12px' }}>
          <span style={{
            color: '#E84545',
            fontSize: 24,
            fontWeight: 800,
            fontFamily: 'Inter, sans-serif',
            letterSpacing: 1,
            textTransform: 'uppercase',
          }}>
            {chartData.title}
          </span>
        </div>
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          style={{
            width: chartWidth,
            height: chartHeight,
            maxWidth: '100%',
            height: 'auto',
          }}
        >
          <defs>
            <linearGradient id={`barGradient${chartData.title.replace(/\s/g, '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#E84545" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#E84545" stopOpacity="0.5" />
            </linearGradient>
            <linearGradient id={`areaGradient${chartData.title.replace(/\s/g, '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#E84545" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#E84545" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          <line x1={padding.left} y1={chartHeight - padding.bottom} x2={chartWidth - padding.right} y2={chartHeight - padding.bottom} stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={chartHeight - padding.bottom} stroke="rgba(255,255,255,0.3)" strokeWidth="2" />

          {[0, 0.25, 0.5, 0.75, 1].map((fraction, i) => {
            const y = chartHeight - padding.bottom - fraction * (chartHeight - padding.top - padding.bottom);
            const value = Math.round(maxValue * fraction);
            return (
              <g key={i}>
                <line x1={padding.left} y1={y} x2={chartWidth - padding.right} y2={y} stroke="rgba(255,255,255,0.1)" strokeWidth="1" strokeDasharray="4 4" />
                <text x={padding.left - 12} y={y + 5} fill="rgba(255,255,255,0.6)" fontSize="14" fontFamily="Inter, sans-serif" textAnchor="end">
                  {value}
                </text>
              </g>
            );
          })}

          {bars.map((bar, i) => (
            <g key={i}>
              <rect
                x={bar.x}
                y={bar.y}
                width={bar.width}
                height={bar.height}
                rx="8"
                fill={`url(#barGradient${chartData.title.replace(/\s/g, '')})`}
              />
              <text
                x={bar.x + bar.width / 2}
                y={bar.y - 10}
                fill="white"
                fontSize="18"
                fontWeight="700"
                fontFamily="Inter, sans-serif"
                textAnchor="middle"
              >
                {bar.point.value}{bar.point.unit || ''}
              </text>
              <text
                x={bar.x + bar.width / 2}
                y={chartHeight - padding.bottom + 28}
                fill="rgba(255,255,255,0.8)"
                fontSize="13"
                fontWeight="600"
                fontFamily="Inter, sans-serif"
                textAnchor="middle"
              >
                {bar.point.label}
              </text>
            </g>
          ))}

          {chartData.type === "line" && (
            <path d={pathD} fill="none" stroke="#E84545" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
          )}
        </svg>
      </div>
    </AbsoluteFill>
  );
};

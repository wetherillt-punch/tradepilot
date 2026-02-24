"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickData,
  HistogramData,
  IChartApi,
  ISeriesApi,
  ColorType,
  CrosshairMode,
  PriceLineOptions,
  LineStyle,
  Time,
} from "lightweight-charts";

export interface TradeLevels {
  entryLow?: number;
  entryHigh?: number;
  stopLoss?: number;
  targets?: Array<{ price: number; label: string }>;
  direction?: string;
}

interface Props {
  candles: CandlestickData<Time>[];
  volumes: HistogramData<Time>[];
  ticker: string;
  levels?: TradeLevels;
  height?: number;
}

export default function CandlestickChart({ candles, volumes, ticker, levels, height = 420 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [crosshairData, setCrosshairData] = useState<{
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    change: number;
    changePct: number;
  } | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    // Clear previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#12121a" },
        textColor: "#666677",
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1a1a28" },
        horzLines: { color: "#1a1a28" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "#3b82f680",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#3b82f6",
        },
        horzLine: {
          color: "#3b82f680",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#3b82f6",
        },
      },
      rightPriceScale: {
        borderColor: "#2a2a3a",
        scaleMargins: { top: 0.05, bottom: 0.2 },
      },
      timeScale: {
        borderColor: "#2a2a3a",
        timeVisible: false,
        rightOffset: 5,
        barSpacing: 8,
        minBarSpacing: 4,
      },
    });

    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef444499",
      wickUpColor: "#22c55e99",
    });
    candleSeries.setData(candles);
    candleSeriesRef.current = candleSeries;

    // Volume series
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    volumeSeries.setData(volumes);

    // ── Trade Level Overlays ──────────────────────────────────────────

    if (levels) {
      const lineBase: Partial<PriceLineOptions> = {
        axisLabelVisible: true,
        lineWidth: 1,
      };

      // Entry zone lines
      if (levels.entryLow) {
        candleSeries.createPriceLine({
          ...lineBase,
          price: levels.entryLow,
          color: "#3b82f6",
          lineStyle: LineStyle.Dashed,
          lineWidth: 2,
          title: `Entry Low $${levels.entryLow}`,
        } as PriceLineOptions);
      }
      if (levels.entryHigh && levels.entryHigh !== levels.entryLow) {
        candleSeries.createPriceLine({
          ...lineBase,
          price: levels.entryHigh,
          color: "#3b82f6",
          lineStyle: LineStyle.Dashed,
          lineWidth: 2,
          title: `Entry High $${levels.entryHigh}`,
        } as PriceLineOptions);
      }

      // Stop loss
      if (levels.stopLoss) {
        candleSeries.createPriceLine({
          ...lineBase,
          price: levels.stopLoss,
          color: "#ef4444",
          lineStyle: LineStyle.Solid,
          lineWidth: 2,
          title: `Stop $${levels.stopLoss}`,
        } as PriceLineOptions);
      }

      // Targets
      if (levels.targets) {
        levels.targets.forEach((t, i) => {
          candleSeries.createPriceLine({
            ...lineBase,
            price: t.price,
            color: "#22c55e",
            lineStyle: LineStyle.Dotted,
            lineWidth: 2,
            title: t.label || `TP${i + 1} $${t.price}`,
          } as PriceLineOptions);
        });
      }
    }

    // ── Crosshair data for legend ────────────────────────────────────

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setCrosshairData(null);
        return;
      }
      const data = param.seriesData.get(candleSeries) as CandlestickData<Time> | undefined;
      const vol = param.seriesData.get(volumeSeries) as HistogramData<Time> | undefined;
      if (data) {
        const change = data.close - data.open;
        const changePct = (change / data.open) * 100;
        setCrosshairData({
          time: String(param.time),
          open: data.open,
          high: data.high,
          low: data.low,
          close: data.close,
          volume: vol?.value || 0,
          change,
          changePct,
        });
      }
    });

    // Fit to 90 most recent candles
    const visibleBars = Math.min(90, candles.length);
    chart.timeScale().setVisibleLogicalRange({
      from: candles.length - visibleBars,
      to: candles.length,
    });

    // Resize handler
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, volumes, levels, height]);

  // Last candle for default legend
  const lastCandle = candles.length > 0 ? candles[candles.length - 1] : null;
  const display = crosshairData || (lastCandle ? {
    time: String(lastCandle.time),
    open: lastCandle.open,
    high: lastCandle.high,
    low: lastCandle.low,
    close: lastCandle.close,
    volume: 0,
    change: lastCandle.close - lastCandle.open,
    changePct: ((lastCandle.close - lastCandle.open) / lastCandle.open) * 100,
  } : null);

  return (
    <div className="bg-bg-secondary border border-border-primary rounded-lg overflow-hidden">
      {/* Legend Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border-primary">
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold font-mono text-text-primary">{ticker}</span>
          <span className="text-xs text-text-muted">Daily</span>
        </div>
        {display && (
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-text-muted">
              O <span className="text-text-secondary">{display.open.toFixed(2)}</span>
            </span>
            <span className="text-text-muted">
              H <span className="text-text-secondary">{display.high.toFixed(2)}</span>
            </span>
            <span className="text-text-muted">
              L <span className="text-text-secondary">{display.low.toFixed(2)}</span>
            </span>
            <span className="text-text-muted">
              C <span className={display.change >= 0 ? "text-accent-green" : "text-accent-red"}>
                {display.close.toFixed(2)}
              </span>
            </span>
            <span className={`${display.change >= 0 ? "text-accent-green" : "text-accent-red"}`}>
              {display.change >= 0 ? "+" : ""}{display.changePct.toFixed(2)}%
            </span>
            {display.volume > 0 && (
              <span className="text-text-muted">
                Vol <span className="text-text-secondary">{formatVolume(display.volume)}</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Chart Canvas */}
      <div ref={containerRef} />

      {/* Level Legend (below chart) */}
      {levels && (
        <div className="flex items-center gap-4 px-4 py-2 border-t border-border-primary text-xs font-mono">
          {(levels.entryLow || levels.entryHigh) && (
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-accent-blue inline-block" style={{ borderTop: "2px dashed #3b82f6" }} />
              <span className="text-accent-blue">Entry Zone</span>
            </span>
          )}
          {levels.stopLoss && (
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 inline-block" style={{ borderTop: "2px solid #ef4444" }} />
              <span className="text-accent-red">Stop ${levels.stopLoss}</span>
            </span>
          )}
          {levels.targets?.map((t, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 inline-block" style={{ borderTop: "2px dotted #22c55e" }} />
              <span className="text-accent-green">{t.label}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(1) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return String(v);
}

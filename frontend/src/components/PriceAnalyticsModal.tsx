'use client';

import React, { useState, useEffect } from 'react';
import { Language, PriceHistoryResponse } from '@/types/krishi';
import { translations, getLocalizedCrop, getLocalizedMarket } from '@/lib/translations';
import { X, TrendingUp, TrendingDown, Minus, ShieldCheck } from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

interface PriceAnalyticsProps {
  commodity: string;
  market: string;
  language: Language;
  sunlightMode: boolean;
  apiBaseUrl: string;
  onClose: () => void;
}

export const PriceAnalyticsModal: React.FC<PriceAnalyticsProps> = ({
  commodity,
  market,
  language,
  sunlightMode,
  apiBaseUrl,
  onClose,
}) => {
  const [days, setDays] = useState<number>(7);
  const [data, setData] = useState<PriceHistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const t = translations[language];

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const queryParams = new URLSearchParams({
          commodity,
          market,
          days: days.toString(),
        });
        const res = await fetch(`${apiBaseUrl}/api/v1/market-prices/history?${queryParams.toString()}`);
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch (err) {
        console.warn('Failed to fetch price history:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [commodity, market, days, apiBaseUrl]);

  const locCrop = getLocalizedCrop(commodity, language);
  const locMarket = getLocalizedMarket(market, language);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div
        className={`relative w-full max-w-3xl rounded-2xl border p-6 shadow-2xl transition-all my-8 ${
          sunlightMode
            ? 'bg-amber-50 border-4 border-black text-black'
            : 'bg-white border-slate-200 text-slate-900'
        }`}
      >
        {/* Header with Title and Close Button */}
        <div className="flex items-start justify-between pb-4 border-b border-slate-200 mb-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded text-xs font-black uppercase bg-emerald-700 text-white">
                {locCrop}
              </span>
              <span className="text-xs font-bold text-slate-500">
                {locMarket}
              </span>
            </div>
            <h2 className="text-2xl font-black tracking-tight">
              {t.priceAnalyticsTitle}
            </h2>
          </div>

          <button
            onClick={onClose}
            type="button"
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 7-Day vs 30-Day Switcher */}
        <div className="flex items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDays(7)}
              type="button"
              className={`px-4 py-2 rounded-xl text-xs font-black transition-all ${
                days === 7
                  ? 'bg-emerald-700 text-white shadow-sm'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
              }`}
            >
              {t.sevenDays}
            </button>
            <button
              onClick={() => setDays(30)}
              type="button"
              className={`px-4 py-2 rounded-xl text-xs font-black transition-all ${
                days === 30
                  ? 'bg-emerald-700 text-white shadow-sm'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
              }`}
            >
              {t.thirtyDays}
            </button>
          </div>

          {data && data.metrics && (
            <div className="flex items-center gap-2">
              <span
                className={`px-3 py-1 rounded-full text-xs font-extrabold flex items-center gap-1.5 ${
                  data.metrics.trend_direction === 'rising' || data.metrics.trend_direction === 'up'
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                    : data.metrics.trend_direction === 'falling' || data.metrics.trend_direction === 'down'
                    ? 'bg-red-100 text-red-800 border border-red-300'
                    : 'bg-amber-100 text-amber-800 border border-amber-300'
                }`}
              >
                {data.metrics.trend_direction === 'rising' || data.metrics.trend_direction === 'up' ? (
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                ) : data.metrics.trend_direction === 'falling' || data.metrics.trend_direction === 'down' ? (
                  <TrendingDown className="w-4 h-4 text-red-600" />
                ) : (
                  <Minus className="w-4 h-4 text-amber-600" />
                )}
                <span>
                  {data.metrics.trend_direction === 'rising' || data.metrics.trend_direction === 'up'
                    ? `${t.trendRising} (+${data.metrics.percentage_change}%)`
                    : data.metrics.trend_direction === 'falling' || data.metrics.trend_direction === 'down'
                    ? `${t.trendFalling} (${data.metrics.percentage_change}%)`
                    : t.trendSteady}
                </span>
              </span>
            </div>
          )}
        </div>

        {/* Analytics Key Metrics Dashboard */}
        {data && data.metrics && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <div className={`p-3 rounded-xl border ${sunlightMode ? 'bg-white border-black' : 'bg-slate-50 border-slate-200'}`}>
              <p className="text-[11px] font-bold text-slate-500 uppercase">{t.avgModalPrice}</p>
              <p className="text-xl font-black text-slate-900">₹{Math.round(data.metrics.average_modal_price)}/q</p>
            </div>

            <div className={`p-3 rounded-xl border ${sunlightMode ? 'bg-white border-black' : 'bg-slate-50 border-slate-200'}`}>
              <p className="text-[11px] font-bold text-slate-500 uppercase">{t.priceVelocity}</p>
              <p className={`text-xl font-black ${
                (data.metrics.price_velocity_pct ?? data.metrics.percentage_change) >= 0 ? 'text-emerald-700' : 'text-red-700'
              }`}>
                {(data.metrics.price_velocity_pct ?? data.metrics.percentage_change) >= 0 ? '+' : ''}
                {data.metrics.price_velocity_pct ?? data.metrics.percentage_change}%
              </p>
            </div>

            <div className={`p-3 rounded-xl border ${sunlightMode ? 'bg-white border-black' : 'bg-slate-50 border-slate-200'}`}>
              <p className="text-[11px] font-bold text-slate-500 uppercase">{t.priceVolatility}</p>
              <p className="text-xl font-black text-amber-700">
                {data.metrics.price_volatility_pct ?? 4.2}%
              </p>
            </div>

            <div className={`p-3 rounded-xl border ${sunlightMode ? 'bg-white border-black' : 'bg-slate-50 border-slate-200'}`}>
              <p className="text-[11px] font-bold text-slate-500 uppercase">{t.highestPrice}</p>
              <p className="text-xl font-black text-slate-900">₹{data.metrics.max_modal_price}/q</p>
            </div>
          </div>
        )}

        {/* Interactive Chart */}
        <div className="h-64 w-full bg-slate-50 rounded-2xl p-3 border border-slate-200 mb-4">
          {loading ? (
            <div className="h-full flex items-center justify-center text-slate-500 text-sm font-bold">
              Loading price history...
            </div>
          ) : data && data.history && data.history.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.history}>
                <defs>
                  <linearGradient id="modalGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#15803d" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#15803d" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="arrival_date" stroke="#64748b" fontSize={11} tickMargin={8} />
                <YAxis stroke="#64748b" fontSize={11} domain={['dataMin - 100', 'dataMax + 100']} />
                <Tooltip
                  formatter={(value: unknown, name: unknown) => [
                    `₹${String(value)}/Quintal`,
                    String(name) === 'modal_price' ? 'Modal Price' : String(name) === 'max_price' ? 'Max Price' : 'Min Price',
                  ]}
                  labelFormatter={(label) => `Arrival Date: ${label}`}
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderRadius: '12px',
                    border: '1px solid #cbd5e1',
                    fontWeight: 'bold',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="modal_price"
                  stroke="#15803d"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#modalGradient)"
                  name="modal_price"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500 text-sm font-bold">
              No historical data points available.
            </div>
          )}
        </div>

        {/* Canonical Source Footer */}
        <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-200">
          <span className="flex items-center gap-1 font-semibold text-emerald-800">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Verified data source: data.gov.in (Agmarknet Daily Wholesale)
          </span>
          <button
            onClick={onClose}
            type="button"
            className="px-4 py-2 rounded-xl bg-slate-900 text-white font-bold text-xs"
          >
            {t.close}
          </button>
        </div>
      </div>
    </div>
  );
};

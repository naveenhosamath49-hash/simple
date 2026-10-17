'use client';

import React, { useState } from 'react';
import { Language, MarketPriceRecord } from '@/types/krishi';
import { translations, getLocalizedCrop, getLocalizedMarket } from '@/lib/translations';
import { VoiceSearch } from '@/components/VoiceSearch';
import {
  Search,
  TrendingUp,
  TrendingDown,
  Minus,
  LineChart,
  BellPlus,
  ShieldCheck,
  Calendar,
  MapPin,
  RefreshCw,
} from 'lucide-react';

interface MandiPriceBoardProps {
  records: MarketPriceRecord[];
  language: Language;
  sunlightMode: boolean;
  loading: boolean;
  onRefresh: () => void;
  onSelectAnalytics: (commodity: string, market: string) => void;
  onSelectAlert: (commodity: string, market: string) => void;
}

const CROP_QUICK_FILTERS = [
  'All',
  'Tomato',
  'Onion',
  'Potato',
  'Green Chilli',
  'Wheat',
  'Rice',
  'Cotton',
];

const STATE_FILTERS = [
  'All States',
  'Karnataka',
  'Maharashtra',
  'Uttar Pradesh',
  'NCT of Delhi',
  'Punjab',
  'Gujarat',
];

export const MandiPriceBoard: React.FC<MandiPriceBoardProps> = ({
  records,
  language,
  sunlightMode,
  loading,
  onRefresh,
  onSelectAnalytics,
  onSelectAlert,
}) => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedCrop, setSelectedCrop] = useState<string>('All');
  const [selectedState, setSelectedState] = useState<string>('All States');

  const t = translations[language];

  // Client-side filtering across commodity, market, district, state
  const filteredRecords = records.filter((r) => {
    const matchesCrop =
      selectedCrop === 'All' || r.commodity.toLowerCase() === selectedCrop.toLowerCase();
    const matchesState =
      selectedState === 'All States' || r.state.toLowerCase() === selectedState.toLowerCase();

    if (!searchTerm.trim()) {
      return matchesCrop && matchesState;
    }

    const term = searchTerm.toLowerCase();
    const matchesSearch =
      r.commodity.toLowerCase().includes(term) ||
      r.market.toLowerCase().includes(term) ||
      r.district.toLowerCase().includes(term) ||
      r.state.toLowerCase().includes(term);

    return matchesCrop && matchesState && matchesSearch;
  });

  const handleVoiceTranscript = (text: string) => {
    setSearchTerm(text);
  };

  return (
    <div className="space-y-5">
      {/* Search Bar & Voice Input Row */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-3.5 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={t.searchPlaceholder}
            className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-bold transition-all focus:outline-none focus:ring-2 focus:ring-emerald-600 ${
              sunlightMode
                ? 'bg-white border-2 border-black text-black placeholder:text-slate-600'
                : 'bg-white border-slate-300 text-slate-900 placeholder:text-slate-400'
            }`}
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              type="button"
              className="absolute right-3 top-3 text-xs font-black px-2 py-0.5 rounded bg-slate-200 text-slate-700"
            >
              ✕
            </button>
          )}
        </div>

        {/* Multilingual Voice Search Button */}
        <VoiceSearch
          language={language}
          onTranscript={handleVoiceTranscript}
          sunlightMode={sunlightMode}
        />

        {/* State Filter Dropdown */}
        <select
          value={selectedState}
          onChange={(e) => setSelectedState(e.target.value)}
          className={`py-3 px-3 rounded-xl border text-xs font-bold transition-all focus:outline-none focus:ring-2 focus:ring-emerald-600 ${
            sunlightMode
              ? 'bg-white border-2 border-black text-black'
              : 'bg-white border-slate-300 text-slate-800'
          }`}
        >
          {STATE_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        {/* Refresh button */}
        <button
          onClick={onRefresh}
          type="button"
          title="Refresh prices"
          className="p-3 rounded-xl bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-700 flex items-center justify-center font-bold"
        >
          <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Quick Filter Crop Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
        {CROP_QUICK_FILTERS.map((crop) => {
          const isSelected = selectedCrop === crop;
          const locName = crop === 'All' ? t.filterAllCrops : getLocalizedCrop(crop, language);

          return (
            <button
              key={crop}
              onClick={() => setSelectedCrop(crop)}
              type="button"
              className={`px-3.5 py-1.5 rounded-full text-xs font-extrabold whitespace-nowrap transition-all border ${
                isSelected
                  ? sunlightMode
                    ? 'bg-black text-amber-300 border-black shadow-md'
                    : 'bg-emerald-800 text-white border-emerald-900 shadow-sm'
                  : sunlightMode
                  ? 'bg-white text-black border-black hover:bg-amber-100'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-300'
              }`}
            >
              {locName}
            </button>
          );
        })}
      </div>

      {/* Records Count Header */}
      <div className="flex items-center justify-between text-xs font-black uppercase tracking-wider text-slate-500 px-1">
        <span>
          Showing {filteredRecords.length} APMC Mandi Rates
        </span>
        <span className="flex items-center gap-1 text-emerald-800 font-extrabold">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          {t.verifiedAgmarknet}
        </span>
      </div>

      {/* Grid of Sunlight-Readable APMC Price Cards */}
      {filteredRecords.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-base font-bold text-slate-600">{t.noRecordsFound}</p>
          <button
            onClick={() => {
              setSearchTerm('');
              setSelectedCrop('All');
              setSelectedState('All States');
            }}
            type="button"
            className="mt-3 px-4 py-2 rounded-xl bg-emerald-700 text-white font-bold text-xs"
          >
            {t.clearFilters}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRecords.map((r) => {
            const locCrop = getLocalizedCrop(r.commodity, language);
            const locMandi = getLocalizedMarket(r.market, language);
            const isRising = r.trend === 'rising' || r.trend_direction === 'rising' || r.trend_direction === 'up';
            const isFalling = r.trend === 'falling' || r.trend_direction === 'falling' || r.trend_direction === 'down';

            return (
              <div
                key={`${r.id}-${r.market}-${r.commodity}`}
                className={`rounded-2xl border p-5 transition-all shadow-sm flex flex-col justify-between ${
                  sunlightMode
                    ? 'bg-amber-50 border-2 border-black text-black ring-1 ring-black shadow-md'
                    : 'bg-white border-slate-200 text-slate-900 hover:border-emerald-300 hover:shadow-md'
                }`}
              >
                <div>
                  {/* Top Bar: Crop Name & Trend Badge */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h3 className="text-lg font-black tracking-tight text-slate-900 flex items-center gap-1.5">
                        <span>{locCrop}</span>
                        {language !== 'en' && (
                          <span className="text-xs font-semibold text-slate-500">
                            ({r.commodity})
                          </span>
                        )}
                      </h3>
                      <div className="flex items-center gap-1 text-xs font-bold text-slate-600 mt-0.5">
                        <MapPin className="w-3.5 h-3.5 text-emerald-700 flex-shrink-0" />
                        <span>
                          {locMandi}, {r.district} ({r.state})
                        </span>
                      </div>
                    </div>

                    {/* Trend Badge */}
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-black flex items-center gap-1 whitespace-nowrap ${
                        isRising
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                          : isFalling
                          ? 'bg-red-100 text-red-800 border border-red-300'
                          : 'bg-amber-100 text-amber-800 border border-amber-300'
                      }`}
                    >
                      {isRising ? (
                        <TrendingUp className="w-3.5 h-3.5 text-emerald-700" />
                      ) : isFalling ? (
                        <TrendingDown className="w-3.5 h-3.5 text-red-700" />
                      ) : (
                        <Minus className="w-3.5 h-3.5 text-amber-700" />
                      )}
                      <span>
                        {isRising
                          ? `${t.trendRising} ${r.percentage_change ? `+${r.percentage_change}%` : ''}`
                          : isFalling
                          ? `${t.trendFalling} ${r.percentage_change ? `${r.percentage_change}%` : ''}`
                          : t.trendSteady}
                      </span>
                    </span>
                  </div>

                  {/* Primary Modal Price Banner */}
                  <div className={`my-3 p-3 rounded-xl border flex items-baseline justify-between ${
                    sunlightMode
                      ? 'bg-white border-2 border-black'
                      : 'bg-emerald-50/70 border-emerald-200'
                  }`}>
                    <div>
                      <span className="text-[11px] font-black uppercase text-emerald-800 block">
                        {t.modalPrice}
                      </span>
                      <span className="text-3xl font-black text-emerald-950">
                        ₹{Math.round(r.modal_price)}
                      </span>
                      <span className="text-xs font-bold text-emerald-800 ml-1">
                        /Quintal
                      </span>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-bold text-slate-500 uppercase block">
                        Range (Min - Max)
                      </span>
                      <span className="text-xs font-black text-slate-800">
                        ₹{Math.round(r.min_price)} - ₹{Math.round(r.max_price)}
                      </span>
                    </div>
                  </div>

                  {/* Metadata: Variety, Grade, Arrival Date */}
                  <div className="flex items-center justify-between text-[11px] font-bold text-slate-500 py-1">
                    <span>
                      {r.variety || 'Local'} • {r.grade || 'FAQ'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-slate-400" />
                      {r.arrival_date}
                    </span>
                  </div>
                </div>

                {/* Bottom Action Buttons */}
                <div className="mt-4 pt-3 border-t border-slate-200 grid grid-cols-2 gap-2">
                  <button
                    onClick={() => onSelectAnalytics(r.commodity, r.market)}
                    type="button"
                    className="py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-black flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <LineChart className="w-3.5 h-3.5 text-emerald-700" />
                    <span>{t.viewHistoryChart}</span>
                  </button>

                  <button
                    onClick={() => onSelectAlert(r.commodity, r.market)}
                    type="button"
                    className="py-2 px-3 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-black flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                  >
                    <BellPlus className="w-3.5 h-3.5" />
                    <span>{t.setAlertForCrop}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

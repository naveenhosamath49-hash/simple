/* eslint-disable @next/next/no-img-element */
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Language, MarketPriceRecord } from '@/types/krishi';
import { translations } from '@/lib/translations';
import { getCachedPrices, saveCachedPrices } from '@/lib/offlineStorage';
import { Header } from '@/components/Header';
import { MandiPriceBoard } from '@/components/MandiPriceBoard';
import { WeatherAdvisoryCard } from '@/components/WeatherAdvisoryCard';
import { PriceAnalyticsModal } from '@/components/PriceAnalyticsModal';
import { PriceAlertsModal } from '@/components/PriceAlertsModal';
import { AICopilotDrawer } from '@/components/AICopilotDrawer';
import {
  WifiOff,
  CloudSun,
  Bell,
  Bot,
  Sun,
  TrendingUp,
  ShieldCheck,
  Sparkles,
  Layers,
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const BG_OPTIONS = [
  { id: '/farmers-working.jpg', label: '🌾 Farmers Working (Real Photo)' },
  { id: '/farmers-field.jpg', label: '🚜 Agricultural Land (Real Photo)' },
  { id: '/farmers-bg.svg', label: '🎨 Sunrise Mandi (Illustration)' },
];

export default function Home() {
  const [language, setLanguage] = useState<Language>('en');
  const [sunlightMode, setSunlightMode] = useState<boolean>(false);
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [records, setRecords] = useState<MarketPriceRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [bgImage, setBgImage] = useState<string>('/farmers-working.jpg');

  // Modals & Drawers state
  const [analyticsTarget, setAnalyticsTarget] = useState<{
    commodity: string;
    market: string;
  } | null>(null);
  const [alertTarget, setAlertTarget] = useState<{
    commodity: string;
    market: string;
  } | null>(null);
  const [showAICopilot, setShowAICopilot] = useState<boolean>(false);
  const [showWeatherSection, setShowWeatherSection] = useState<boolean>(true);

  const t = translations[language];

  // 1. Initialize PWA Service Worker & Online Listener
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsOnline(navigator.onLine);

      const handleOnline = () => setIsOnline(true);
      const handleOffline = () => setIsOnline(false);

      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);

      // Register PWA Service Worker
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker
          .register('/sw.js')
          .then((reg) => console.log('Service Worker registered successfully:', reg.scope))
          .catch((err) => console.warn('Service Worker registration skipped/failed:', err));
      }

      // Restore user preferences
      const savedLang = localStorage.getItem('krishimandi_lang') as Language;
      if (savedLang && ['en', 'hi', 'kn'].includes(savedLang)) {
        setLanguage(savedLang);
      }

      const savedSunlight = localStorage.getItem('krishimandi_sunlight') === 'true';
      setSunlightMode(savedSunlight);

      const savedBg = localStorage.getItem('krishimandi_bg');
      if (savedBg && BG_OPTIONS.some((o) => o.id === savedBg)) {
        setBgImage(savedBg);
      }

      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }
  }, []);

  const handleLanguageChange = (newLang: Language) => {
    setLanguage(newLang);
    if (typeof window !== 'undefined') {
      localStorage.setItem('krishimandi_lang', newLang);
    }
  };

  const handleToggleSunlightMode = () => {
    const nextVal = !sunlightMode;
    setSunlightMode(nextVal);
    if (typeof window !== 'undefined') {
      localStorage.setItem('krishimandi_sunlight', String(nextVal));
    }
  };

  const handleBgChange = (newBg: string) => {
    setBgImage(newBg);
    if (typeof window !== 'undefined') {
      localStorage.setItem('krishimandi_bg', newBg);
    }
  };

  // 2. Fetch canonical APMC Mandi prices
  const fetchMarketPrices = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/market-prices?limit=100&includeTrend=true`);
      if (!res.ok) {
        throw new Error(`API responded with ${res.status}`);
      }
      const data = await res.json();
      if (data && Array.isArray(data.records) && data.records.length > 0) {
        setRecords(data.records);
        saveCachedPrices(data.records);
      } else {
        throw new Error('Empty records array');
      }
    } catch (err) {
      console.warn('Network fetch failed. Loading offline snapshot from local storage:', err);
      const cached = getCachedPrices();
      setRecords(cached);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMarketPrices();
  }, [fetchMarketPrices]);

  // Key ticker records for quick price snapshot
  const tickerItems = records.slice(0, 6);

  return (
    <div
      className={`relative min-h-screen flex flex-col transition-colors ${
        sunlightMode ? 'bg-amber-100 font-bold' : 'bg-slate-900/5'
      }`}
    >
      {/* Ambient Agricultural Land Background Texture */}
      {!sunlightMode && (
        <div
          className="fixed inset-0 pointer-events-none z-0 opacity-15 bg-cover bg-center bg-fixed transition-all duration-700"
          style={{ backgroundImage: `url(${bgImage})` }}
          aria-hidden="true"
        />
      )}

      {/* 1. Global Navigation & Sunlight Header */}
      <Header
        language={language}
        onLanguageChange={handleLanguageChange}
        sunlightMode={sunlightMode}
        onToggleSunlightMode={handleToggleSunlightMode}
        isOnline={isOnline}
        onOpenAlerts={() => setAlertTarget({ commodity: 'Tomato', market: 'Mysore' })}
        onOpenAI={() => setShowAICopilot(true)}
        onOpenWeather={() => setShowWeatherSection((prev) => !prev)}
      />

      {/* 2. Offline Mode Banner */}
      {!isOnline && (
        <div className="relative z-20 bg-amber-500 text-black px-4 py-2 font-black text-xs sm:text-sm flex items-center justify-center gap-2 shadow-inner">
          <WifiOff className="w-4 h-4 text-black animate-pulse" />
          <span>{t.offlineNotice}</span>
        </div>
      )}

      {/* 3. Hero Showcase: Farmers Working in Land */}
      <section
        aria-label="KrishiMandi Hero"
        className="relative z-10 w-full overflow-hidden shadow-2xl border-b-4 border-amber-400"
        style={{ minHeight: '340px' }}
      >
        {/* Real Farmers Background Image */}
        <img
          src={bgImage}
          alt="Indian farmers working in agricultural land"
          className="absolute inset-0 w-full h-full object-cover object-center select-none"
        />

        {/* Dual Layer Cinematic Gradients for Ultra-Clear Sunlight & Normal Readability */}
        <div className="absolute inset-0 bg-gradient-to-r from-emerald-950/95 via-emerald-900/80 to-emerald-950/70" />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-black/40" />

        {/* Hero Content */}
        <div className="relative z-10 max-w-7xl mx-auto px-4 py-8 sm:py-12 flex flex-col justify-between h-full">
          {/* Top Row: Mission Badges & Background Selector */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 bg-amber-400/25 border border-amber-400/60 text-amber-300 text-xs font-black px-3 py-1 rounded-full tracking-wider uppercase backdrop-blur-md shadow-md">
                🌾 Agmarknet Daily • Open-Meteo • NVIDIA NIM
              </span>
              <span className="hidden sm:inline-flex items-center gap-1 bg-emerald-500/20 border border-emerald-400/40 text-emerald-200 text-xs font-bold px-2.5 py-1 rounded-full backdrop-blur-md">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                Zero Distress Selling Guarantee
              </span>
            </div>

            {/* Background Image Switcher Control */}
            <div className="flex items-center gap-1 bg-black/50 backdrop-blur-md p-1 rounded-xl border border-white/10">
              <span className="text-[10px] font-bold text-amber-300 px-2 flex items-center gap-1">
                <Layers className="w-3 h-3" />
                Theme:
              </span>
              {BG_OPTIONS.map((opt, idx) => (
                <button
                  key={opt.id}
                  onClick={() => handleBgChange(opt.id)}
                  type="button"
                  title={opt.label}
                  className={`text-[11px] font-black px-2.5 py-1 rounded-lg transition-all ${
                    bgImage === opt.id
                      ? 'bg-amber-400 text-emerald-950 shadow-md font-black'
                      : 'text-slate-300 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {idx === 0 ? '🌾 Paddy' : idx === 1 ? '🚜 Land' : '🎨 Art'}
                </button>
              ))}
            </div>
          </div>

          {/* Center: Trilingual App Title & Mission Tagline */}
          <div className="text-center sm:text-left my-2 space-y-2">
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-white tracking-tight drop-shadow-xl flex flex-wrap items-baseline gap-2 sm:gap-3">
              <span className="text-amber-300 font-black">कृषि मंडी</span>
              <span className="text-white/40 font-light">|</span>
              <span className="text-emerald-300 font-black">ಕೃಷಿ ಮಂಡಿ</span>
              <span className="text-white/40 font-light">|</span>
              <span className="text-white">KrishiMandi Intelligence</span>
            </h1>

            <p className="text-sm sm:text-base text-slate-200 font-semibold max-w-3xl drop-shadow-md leading-relaxed">
              Empowering Indian farmers and FPOs with real-time APMC Mandi wholesale price intelligence, 7d/30d price velocity &amp; volatility analytics, hyperlocal weather risk advisories, and an AI Mandi Advisory Copilot powered by NVIDIA NIM.
            </p>
          </div>

          {/* Quick Action Buttons Row */}
          <div className="flex flex-wrap items-center gap-2.5 mt-5">
            <button
              onClick={() => setShowAICopilot(true)}
              type="button"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-400 hover:bg-amber-300 text-emerald-950 font-black text-xs sm:text-sm shadow-xl transition-all transform hover:-translate-y-0.5"
            >
              <Bot className="w-4 h-4 text-emerald-950" />
              <span>{t.tabAI} (NVIDIA NIM)</span>
            </button>

            <button
              onClick={() => setAlertTarget({ commodity: 'Tomato', market: 'Mysore' })}
              type="button"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-xs sm:text-sm border border-emerald-500/50 shadow-lg backdrop-blur-md transition-all"
            >
              <Bell className="w-4 h-4 text-amber-300" />
              <span>{t.tabAlerts} (Free Push &amp; SMS)</span>
            </button>

            <button
              onClick={() => setShowWeatherSection((prev) => !prev)}
              type="button"
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-bold text-xs sm:text-sm border border-white/20 backdrop-blur-md transition-all"
            >
              <CloudSun className="w-4 h-4 text-blue-300" />
              <span>{showWeatherSection ? 'Hide Weather' : 'Show Weather'}</span>
            </button>

            <button
              onClick={handleToggleSunlightMode}
              type="button"
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold border transition-all ${
                sunlightMode
                  ? 'bg-amber-300 text-black border-amber-400 font-black'
                  : 'bg-black/30 hover:bg-black/50 text-amber-300 border-amber-400/40'
              }`}
            >
              <Sun className="w-4 h-4 text-amber-400" />
              <span>{sunlightMode ? '☀️ High-Contrast ON' : '☀️ Sunlight Mode'}</span>
            </button>
          </div>

          {/* Live Price Ticker Strip */}
          {tickerItems.length > 0 && (
            <div className="mt-6 pt-4 border-t border-white/10 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-black uppercase text-amber-300 flex items-center gap-1 mr-2">
                <Sparkles className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
                Live Rates:
              </span>
              <div className="flex flex-wrap items-center gap-2">
                {tickerItems.map((item) => (
                  <button
                    key={`${item.id}-${item.commodity}-${item.market}`}
                    onClick={() => setAnalyticsTarget({ commodity: item.commodity, market: item.market })}
                    type="button"
                    className="flex items-center gap-1.5 bg-black/40 hover:bg-black/60 border border-white/10 text-white text-xs px-2.5 py-1 rounded-lg transition-all"
                  >
                    <span className="font-bold text-slate-200">{item.commodity}</span>
                    <span className="text-slate-400 text-[10px]">({item.market})</span>
                    <span className="font-black text-amber-300">₹{Math.round(item.modal_price)}/Q</span>
                    <TrendingUp className="w-3 h-3 text-emerald-400" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 4. Main Operational Cockpit */}
      <main className="relative z-10 flex-1 max-w-7xl w-full mx-auto px-4 py-6 space-y-6">
        {/* Banner Tagline & Quick Toggle Row */}
        <div className={`p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-sm ${
          sunlightMode
            ? 'bg-amber-50 border-2 border-black text-black'
            : 'bg-white/95 backdrop-blur-md border-slate-200 text-slate-900'
        }`}>
          <div>
            <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
              {t.tagline}
            </h2>
            <p className="text-xs text-slate-500 font-semibold mt-0.5">
              Authoritative Agmarknet prices • Open-Meteo hyperlocal agromet • NVIDIA NIM AI Copilot
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowWeatherSection((prev) => !prev)}
              type="button"
              className={`text-xs font-bold px-3 py-1.5 rounded-lg border flex items-center gap-1.5 transition-colors ${
                sunlightMode
                  ? 'bg-white border-2 border-black text-black'
                  : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
              }`}
            >
              <CloudSun className="w-3.5 h-3.5 text-blue-600" />
              <span>{showWeatherSection ? 'Hide Weather' : 'Show Weather'}</span>
            </button>
          </div>
        </div>

        {/* 5. Hyperlocal Agricultural Weather Risk Card */}
        {showWeatherSection && (
          <div className={sunlightMode ? '' : 'backdrop-blur-md bg-white/95 rounded-2xl shadow-md border border-slate-200 overflow-hidden'}>
            <WeatherAdvisoryCard
              language={language}
              sunlightMode={sunlightMode}
              apiBaseUrl={API_BASE_URL}
            />
          </div>
        )}

        {/* 6. Canonical APMC Mandi Price Board */}
        <div className={sunlightMode ? '' : 'backdrop-blur-md bg-white/95 p-5 rounded-2xl shadow-md border border-slate-200'}>
          <MandiPriceBoard
            records={records}
            language={language}
            sunlightMode={sunlightMode}
            loading={loading}
            onRefresh={fetchMarketPrices}
            onSelectAnalytics={(comm, mkt) => setAnalyticsTarget({ commodity: comm, market: mkt })}
            onSelectAlert={(comm, mkt) => setAlertTarget({ commodity: comm, market: mkt })}
          />
        </div>
      </main>

      {/* 7. Floating Action Bottom Pill for Handheld Field Usage */}
      <aside
        aria-label="Quick Actions"
        className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 bg-emerald-950/95 backdrop-blur-md text-white px-5 py-2.5 rounded-full shadow-2xl border border-emerald-700 flex items-center gap-4"
      >
        <button
          onClick={() => setShowAICopilot(true)}
          type="button"
          className="flex items-center gap-1.5 text-xs font-black text-amber-300 hover:text-amber-200 transition-colors"
        >
          <Bot className="w-4 h-4 text-amber-300" />
          <span>{t.tabAI}</span>
        </button>
        <span className="w-px h-4 bg-emerald-800" />
        <button
          onClick={() => setAlertTarget({ commodity: 'Tomato', market: 'Mysore' })}
          type="button"
          className="flex items-center gap-1.5 text-xs font-black text-emerald-200 hover:text-white transition-colors"
        >
          <Bell className="w-4 h-4 text-amber-400" />
          <span>{t.tabAlerts}</span>
        </button>
        <span className="w-px h-4 bg-emerald-800" />
        <button
          onClick={handleToggleSunlightMode}
          type="button"
          className="flex items-center gap-1.5 text-xs font-black text-emerald-200 hover:text-white transition-colors"
        >
          <Sun className="w-4 h-4 text-amber-400" />
          <span>{sunlightMode ? 'High-Contrast' : 'Sunlight'}</span>
        </button>
      </aside>

      {/* 8. Modal: Price Velocity & Volatility Analytics (Recharts) */}
      {analyticsTarget && (
        <PriceAnalyticsModal
          commodity={analyticsTarget.commodity}
          market={analyticsTarget.market}
          language={language}
          sunlightMode={sunlightMode}
          apiBaseUrl={API_BASE_URL}
          onClose={() => setAnalyticsTarget(null)}
        />
      )}

      {/* 9. Modal: Automated Price Alerts Management */}
      {alertTarget && (
        <PriceAlertsModal
          initialCommodity={alertTarget.commodity}
          initialMarket={alertTarget.market}
          language={language}
          sunlightMode={sunlightMode}
          apiBaseUrl={API_BASE_URL}
          onClose={() => setAlertTarget(null)}
        />
      )}

      {/* 10. Drawer: NVIDIA NIM Grounded AI Advisory Copilot */}
      {showAICopilot && (
        <AICopilotDrawer
          language={language}
          sunlightMode={sunlightMode}
          apiBaseUrl={API_BASE_URL}
          onClose={() => setShowAICopilot(false)}
        />
      )}

      {/* 11. Footer */}
      <footer className="relative z-10 mt-12 py-6 bg-slate-950 text-slate-400 border-t border-slate-800 text-xs">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="font-semibold text-center sm:text-left">
            KrishiMandi Intelligence (कृषि मंडी / ಕೃಷಿ ಮಂಡಿ) • Free Public Good for Indian Farmers
          </p>
          <div className="flex items-center gap-4 text-slate-400 font-medium">
            <span>data.gov.in Agmarknet</span>
            <span>•</span>
            <span>Open-Meteo Agromet</span>
            <span>•</span>
            <span>NVIDIA NIM LLMs</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

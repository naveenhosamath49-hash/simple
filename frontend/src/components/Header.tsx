'use client';

import React from 'react';
import { Language } from '@/types/krishi';
import { translations } from '@/lib/translations';
import { Sun, Wifi, WifiOff, Bot, Bell, CloudSun } from 'lucide-react';

interface HeaderProps {
  language: Language;
  onLanguageChange: (lang: Language) => void;
  sunlightMode: boolean;
  onToggleSunlightMode: () => void;
  isOnline: boolean;
  onOpenAlerts: () => void;
  onOpenAI: () => void;
  onOpenWeather: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  language,
  onLanguageChange,
  sunlightMode,
  onToggleSunlightMode,
  isOnline,
  onOpenAlerts,
  onOpenAI,
  onOpenWeather,
}) => {
  const t = translations[language];

  return (
    <header className={`sticky top-0 z-40 transition-colors border-b ${
      sunlightMode 
        ? 'bg-emerald-950 text-white border-black shadow-md' 
        : 'bg-emerald-900 text-white border-emerald-800 shadow-sm'
    }`}>
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        {/* Brand identity & localization */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-400 text-emerald-950 flex items-center justify-center font-black text-xl shadow-inner">
              🌾
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl md:text-2xl font-black tracking-tight text-white flex items-center gap-2">
                  <span>{t.appTitle}</span>
                  <span className="text-amber-300 text-sm font-semibold hidden lg:inline">
                    (कृषि मंडी / ಕೃಷಿ ಮಂಡಿ)
                  </span>
                </h1>
              </div>
              <p className="text-xs text-emerald-200 font-medium hidden sm:block">
                {t.appSubtitle}
              </p>
            </div>
          </div>

          {/* Mobile network indicator */}
          <div className="flex md:hidden items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-bold flex items-center gap-1 ${
              isOnline ? 'bg-emerald-800 text-emerald-200' : 'bg-amber-500 text-black animate-pulse'
            }`}>
              {isOnline ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
              {isOnline ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
        </div>

        {/* Global Controls & Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Desktop Online Status */}
          <div className="hidden md:flex items-center">
            <span className={`px-2.5 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 border ${
              isOnline 
                ? 'bg-emerald-800/80 border-emerald-700 text-emerald-100' 
                : 'bg-amber-400 border-amber-500 text-black animate-pulse'
            }`}>
              {isOnline ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
              {isOnline ? 'Agmarknet Connected' : 'Offline Snapshot'}
            </span>
          </div>

          {/* Sunlight Mode Toggle */}
          <button
            onClick={onToggleSunlightMode}
            type="button"
            title="Toggle high-contrast sunlight view"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
              sunlightMode
                ? 'bg-amber-300 text-black border-amber-400 shadow-sm'
                : 'bg-emerald-800 hover:bg-emerald-700 text-white border-emerald-700'
            }`}
          >
            <Sun className="w-3.5 h-3.5" />
            <span>{sunlightMode ? t.sunlightMode : 'Sunlight Boost'}</span>
          </button>

          {/* Language Selector */}
          <div className="flex items-center bg-emerald-950/70 p-0.5 rounded-lg border border-emerald-800">
            <button
              onClick={() => onLanguageChange('en')}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
                language === 'en' ? 'bg-amber-400 text-emerald-950 shadow-sm' : 'text-emerald-200 hover:text-white'
              }`}
            >
              EN
            </button>
            <button
              onClick={() => onLanguageChange('hi')}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
                language === 'hi' ? 'bg-amber-400 text-emerald-950 shadow-sm' : 'text-emerald-200 hover:text-white'
              }`}
            >
              हिंदी
            </button>
            <button
              onClick={() => onLanguageChange('kn')}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
                language === 'kn' ? 'bg-amber-400 text-emerald-950 shadow-sm' : 'text-emerald-200 hover:text-white'
              }`}
            >
              ಕನ್ನಡ
            </button>
          </div>

          {/* Weather shortcut */}
          <button
            onClick={onOpenWeather}
            type="button"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-800/80 hover:bg-emerald-700 border border-emerald-700 text-white"
          >
            <CloudSun className="w-3.5 h-3.5 text-amber-300" />
            <span>{t.tabWeather}</span>
          </button>

          {/* Alerts CTA */}
          <button
            onClick={onOpenAlerts}
            type="button"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-800/80 hover:bg-emerald-700 border border-emerald-700 text-white"
          >
            <Bell className="w-3.5 h-3.5 text-amber-300" />
            <span>{t.tabAlerts}</span>
          </button>

          {/* AI Copilot CTA */}
          <button
            onClick={onOpenAI}
            type="button"
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-extrabold bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-emerald-950 shadow-md transition-all border border-amber-300"
          >
            <Bot className="w-4 h-4" />
            <span>{t.tabAI}</span>
          </button>
        </div>
      </div>
    </header>
  );
};

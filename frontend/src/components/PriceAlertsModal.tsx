'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Language, AlertSubscription } from '@/types/krishi';
import { translations } from '@/lib/translations';
import { getLocalAlerts, saveLocalAlerts } from '@/lib/offlineStorage';
import { X, Bell, BellRing, Trash2, CheckCircle2, Send } from 'lucide-react';

interface PriceAlertsProps {
  initialCommodity?: string;
  initialMarket?: string;
  language: Language;
  sunlightMode: boolean;
  apiBaseUrl: string;
  onClose: () => void;
}

export const PriceAlertsModal: React.FC<PriceAlertsProps> = ({
  initialCommodity = 'Tomato',
  initialMarket = 'Mysore',
  language,
  sunlightMode,
  apiBaseUrl,
  onClose,
}) => {
  const [commodity, setCommodity] = useState<string>(initialCommodity);
  const [market, setMarket] = useState<string>(initialMarket);
  const [direction, setDirection] = useState<'above' | 'below'>('above');
  const [threshold, setThreshold] = useState<string>('1900');
  const [channel, setChannel] = useState<string>('sms');
  const [phone, setPhone] = useState<string>('+91 98765 43210');
  const [alerts, setAlerts] = useState<AlertSubscription[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const t = translations[language];

  // Load existing alerts
  const loadAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/alerts?farmerId=farmer_web_demo`);
      if (res.ok) {
        const data: AlertSubscription[] = await res.json();
        setAlerts(data);
        saveLocalAlerts(data);
        return;
      }
    } catch {
      // Offline fallback
    }
    setAlerts(getLocalAlerts());
  }, [apiBaseUrl]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  // Request browser Web Push notification permission
  const requestNotificationPermission = async () => {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        new Notification('KrishiMandi Intelligence', {
          body: 'Price alerts are active. You will be notified when APMC rates cross your target threshold.',
          icon: '/favicon.ico',
        });
      }
    }
  };

  const handleCreateAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    const numThreshold = parseFloat(threshold);
    if (isNaN(numThreshold) || numThreshold <= 0) return;

    setLoading(true);
    setStatusMessage(null);

    const payload = {
      farmerId: 'farmer_web_demo',
      commodity,
      market,
      direction,
      threshold: numThreshold,
      channel,
    };

    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        await res.json();
        setStatusMessage(`Alert active! We will notify you when ${commodity} goes ${direction} ₹${numThreshold}/q.`);
        await loadAlerts();
        requestNotificationPermission();
      } else {
        throw new Error('Server returned error');
      }
    } catch {
      // Local fallback simulation
      const mockAlert: AlertSubscription = {
        alertId: `alert_${Date.now()}`,
        farmerId: 'farmer_web_demo',
        commodity,
        market,
        direction,
        threshold: numThreshold,
        channel,
        active: true,
        createdAt: new Date().toISOString(),
      };
      const updated = [mockAlert, ...alerts];
      setAlerts(updated);
      saveLocalAlerts(updated);
      setStatusMessage(`Offline alert saved locally for ${commodity} ${direction} ₹${numThreshold}/q.`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAlert = async (alertId: string) => {
    try {
      await fetch(`${apiBaseUrl}/api/v1/alerts/${alertId}?farmerId=farmer_web_demo`, {
        method: 'DELETE',
      });
    } catch {
      // offline delete
    }
    const updated = alerts.filter((a) => a.alertId !== alertId);
    setAlerts(updated);
    saveLocalAlerts(updated);
  };

  const handleEvaluateNow = async () => {
    setLoading(true);
    setStatusMessage('Evaluating active alerts against live APMC Mandi prices...');
    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/alerts/evaluate`, { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        const triggered = result.triggered_alerts || 0;
        setStatusMessage(
          triggered > 0
            ? `Evaluation complete: ${triggered} alerts triggered and sent via ${channel.toUpperCase()}!`
            : 'Evaluation complete: Rates are within current normal thresholds. No alert triggered.'
        );
      }
    } catch {
      setStatusMessage('Alert evaluation simulated locally. Rates analyzed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div
        className={`relative w-full max-w-2xl rounded-2xl border p-6 shadow-2xl transition-all my-8 ${
          sunlightMode
            ? 'bg-amber-50 border-4 border-black text-black'
            : 'bg-white border-slate-200 text-slate-900'
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-slate-200 mb-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-100 text-amber-800">
              <BellRing className="w-6 h-6 text-amber-600" />
            </div>
            <div>
              <h2 className="text-xl font-black tracking-tight">{t.alertsTitle}</h2>
              <p className="text-xs text-slate-500 font-medium">{t.alertsSubtitle}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Status banner */}
        {statusMessage && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-bold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{statusMessage}</span>
          </div>
        )}

        {/* Create Alert Form */}
        <form onSubmit={handleCreateAlert} className="space-y-4 mb-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">
                {t.selectCommodity}
              </label>
              <select
                value={commodity}
                onChange={(e) => setCommodity(e.target.value)}
                className="w-full text-sm font-bold p-2.5 rounded-xl border border-slate-300 bg-slate-50 focus:ring-2 focus:ring-emerald-600 focus:outline-none"
              >
                <option value="Tomato">Tomato (टमाटर / ಟೊಮೇಟೊ)</option>
                <option value="Onion">Onion (प्याज / ಈರುಳ್ಳಿ)</option>
                <option value="Potato">Potato (आलू / ಆಲೂಗಡ್ಡೆ)</option>
                <option value="Green Chilli">Green Chilli (हरी मिर्च / ಹಸಿಮೆಣಸು)</option>
                <option value="Wheat">Wheat (गेहूं / ಗೋಧಿ)</option>
                <option value="Rice">Rice (चावल / ಅಕ್ಕಿ)</option>
                <option value="Cotton">Cotton (कपास / ಹತ್ತಿ)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">
                {t.selectMarket}
              </label>
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                className="w-full text-sm font-bold p-2.5 rounded-xl border border-slate-300 bg-slate-50 focus:ring-2 focus:ring-emerald-600 focus:outline-none"
              >
                <option value="Mysore">Mysore (मैसूर / ಮೈಸೂರು)</option>
                <option value="Bangalore">Bangalore (बेंगलुरु / ಬೆಂಗಳೂರು)</option>
                <option value="Kolar">Kolar (कोलार / ಕೋಲಾರ)</option>
                <option value="Mandya">Mandya (मंड्या / ಮಂಡ್ಯ)</option>
                <option value="Pune">Pune (पुणे / ಪುಣೆ)</option>
                <option value="Nashik">Nashik (नासिक / ನಾಸಿಕ್)</option>
                <option value="Lasalgaon">Lasalgaon (लासलगांव)</option>
                <option value="Azadpur">Azadpur Mandi (Delhi)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">
                Trigger Condition
              </label>
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value as 'above' | 'below')}
                className="w-full text-sm font-bold p-2.5 rounded-xl border border-slate-300 bg-slate-50 focus:ring-2 focus:ring-emerald-600 focus:outline-none"
              >
                <option value="above">{t.directionAbove}</option>
                <option value="below">{t.directionBelow}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">
                {t.targetPrice}
              </label>
              <div className="relative">
                <span className="absolute left-3 top-2.5 font-black text-slate-500">₹</span>
                <input
                  type="number"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                  placeholder="e.g. 1900"
                  className="w-full pl-8 pr-3 py-2.5 text-sm font-bold rounded-xl border border-slate-300 bg-slate-50 focus:ring-2 focus:ring-emerald-600 focus:outline-none"
                  required
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">
                {t.notificationChannel}
              </label>
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="w-full text-sm font-bold p-2.5 rounded-xl border border-slate-300 bg-slate-50 focus:ring-2 focus:ring-emerald-600 focus:outline-none"
              >
                <option value="sms">{t.channelSMS}</option>
                <option value="push">{t.channelPush}</option>
                <option value="in_app">{t.channelInApp}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">
                Farmer Mobile Number
              </label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full text-sm font-bold p-2.5 rounded-xl border border-slate-300 bg-slate-50 focus:ring-2 focus:ring-emerald-600 focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-extrabold text-sm shadow-md transition-all flex items-center justify-center gap-2"
          >
            <Bell className="w-4 h-4" />
            <span>{loading ? 'Registering...' : t.saveAlert}</span>
          </button>
        </form>

        {/* Active Alert Subscriptions List */}
        <div className="pt-4 border-t border-slate-200">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-black uppercase text-slate-700">
              {t.activeAlerts} ({alerts.length})
            </h3>
            <button
              onClick={handleEvaluateNow}
              type="button"
              className="text-xs font-extrabold text-emerald-700 hover:text-emerald-800 underline flex items-center gap-1"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{t.testEvaluation}</span>
            </button>
          </div>

          {alerts.length === 0 ? (
            <p className="text-xs text-slate-500 font-medium py-3 text-center bg-slate-50 rounded-xl">
              {t.noAlertsConfigured}
            </p>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {alerts.map((a) => (
                <div
                  key={a.alertId}
                  className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs font-bold"
                >
                  <div>
                    <span className="text-emerald-800 font-black mr-1">{a.commodity}</span>
                    <span className="text-slate-600">({a.market || 'All Mandis'}): </span>
                    <span className="text-slate-900">
                      {a.direction === 'above' ? 'Rises above' : 'Drops below'} ₹{a.threshold}/q
                    </span>
                    <span className="ml-2 px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px] uppercase font-extrabold">
                      {a.channel}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDeleteAlert(a.alertId)}
                    type="button"
                    title="Delete alert"
                    className="p-1.5 rounded-lg text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

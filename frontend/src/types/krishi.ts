export type Language = 'en' | 'hi' | 'kn';

export interface MarketPriceRecord {
  id: number;
  state: string;
  district: string;
  market: string;
  commodity: string;
  variety: string;
  grade: string;
  arrival_date: string;
  arrivalDate?: string;
  min_price: number;
  max_price: number;
  modal_price: number;
  unit: string;
  source: string;
  trend?: 'rising' | 'falling' | 'steady' | 'up' | 'down';
  trend_direction?: 'rising' | 'falling' | 'steady' | 'up' | 'down';
  percentage_change?: number;
}

export interface MarketPricesResponse {
  records: MarketPriceRecord[];
  total: number;
  limit: number;
  offset: number;
  cached: boolean;
  source: string;
}

export interface HistoryPoint {
  arrival_date: string;
  arrivalDate?: string;
  min_price: number;
  max_price: number;
  modal_price: number;
  market: string;
  state: string;
}

export interface PriceMetrics {
  average_modal_price: number;
  min_modal_price: number;
  max_modal_price: number;
  percentage_change: number;
  price_velocity_pct?: number;
  price_volatility_pct?: number;
  trend_direction: 'rising' | 'falling' | 'steady' | 'up' | 'down';
  time_window_days?: number;
  data_points: number;
}

export interface PriceHistoryResponse {
  commodity: string;
  market: string;
  state: string;
  history: HistoryPoint[];
  metrics: PriceMetrics;
}

export interface WeatherData {
  district: string;
  state: string;
  temperature: number;
  humidity: number;
  rainfall_mm: number;
  wind_speed_kmh: number;
  condition: string;
  advisory: string;
  recorded_at?: string;
}

export interface AlertSubscription {
  alertId: string;
  farmerId: string;
  commodity: string;
  market?: string;
  direction: 'above' | 'below';
  threshold: number;
  channel: string;
  active: boolean;
  createdAt: string;
}

export interface AICitation {
  market: string;
  commodity: string;
  state: string;
  arrival_date: string;
  modal_price: number;
  min_price: number;
  max_price: number;
  source: string;
}

export interface AIChatResponse {
  response: string;
  language: Language;
  grounded: boolean;
  citations: AICitation[];
  provider: string;
}

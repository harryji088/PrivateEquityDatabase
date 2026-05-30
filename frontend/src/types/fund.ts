/** Fund and related types */

export interface FundCompany {
  id: string;
  name: string;
  short_name?: string;
  registration_code?: string;
  total_aum?: number;
  founding_date?: string;
  province?: string;
  city?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface FundManager {
  id: string;
  company_id?: string;
  name: string;
  title?: string;
  experience_years?: number;
  education?: string;
  bio?: string;
  created_at: string;
  updated_at: string;
}

export interface Fund {
  id: string;
  company_id: string;
  manager_id?: string;
  name: string;
  code?: string;
  strategy_type: string;
  inception_date: string;
  status: string;
  aum?: number;
  management_fee_rate?: number;
  performance_fee_rate?: number;
  lockup_period_months: number;
  subscription_frequency?: string;
  redemption_frequency?: string;
  min_subscription_amount?: number;
  benchmark_id?: string;
  description?: string;
  company_name?: string;
  manager_name?: string;
  created_at: string;
  updated_at: string;
}

export type StrategyType =
  | 'stock_long'
  | 'market_neutral'
  | 'cta'
  | 'arbitrage'
  | 'macro_hedge'
  | 'bond'
  | 'multi_strategy'
  | 'fof'
  | 'quant'
  | 'other';

export const STRATEGY_LABELS: Record<string, string> = {
  stock_long: '股票多头',
  market_neutral: '市场中性',
  cta: 'CTA',
  arbitrage: '套利',
  macro_hedge: '宏观对冲',
  bond: '债券',
  multi_strategy: '多策略',
  fof: 'FOF',
  quant: '量化',
  other: '其他',
};

export const FUND_STATUS_LABELS: Record<string, string> = {
  active: '运行中',
  liquidated: '已清盘',
  suspended: '暂停申购',
  pre_issue: '待发行',
};

export interface NavData {
  id: number;
  fund_id: string;
  date: string;
  nav: number;
  cumulative_nav?: number;
  daily_return?: number;
  adjusted_nav?: number;
  created_at: string;
}

export interface Benchmark {
  id: string;
  name: string;
  code?: string;
  category?: string;
  description?: string;
}

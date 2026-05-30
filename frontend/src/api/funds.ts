import client from './client';
import type { Fund, FundCompany, FundManager, NavData, PaginatedResponse } from '../types';

// Funds
export async function fetchFunds(params: Record<string, any> = {}) {
  const { data } = await client.get<PaginatedResponse<Fund>>('/funds', { params });
  return data;
}

export async function fetchFund(id: string) {
  const { data } = await client.get<Fund>(`/funds/${id}`);
  return data;
}

export async function createFund(fund: Partial<Fund>) {
  const { data } = await client.post<Fund>('/funds', fund);
  return data;
}

export async function updateFund(id: string, fund: Partial<Fund>) {
  const { data } = await client.put<Fund>(`/funds/${id}`, fund);
  return data;
}

export async function deleteFund(id: string) {
  await client.delete(`/funds/${id}`);
}

// Companies
export async function fetchCompanies(params: Record<string, any> = {}) {
  const { data } = await client.get<PaginatedResponse<FundCompany>>('/companies', { params });
  return data;
}

export async function createCompany(company: Partial<FundCompany>) {
  const { data } = await client.post<FundCompany>('/companies', company);
  return data;
}

// Managers
export async function fetchManagers(params: Record<string, any> = {}) {
  const { data } = await client.get<PaginatedResponse<FundManager>>('/managers', { params });
  return data;
}

// NAV
export async function fetchNavData(fundId: string, params: Record<string, any> = {}) {
  const { data } = await client.get<PaginatedResponse<NavData>>('/nav', {
    params: { fund_id: fundId, ...params },
  });
  return data;
}

export async function importNavCsv(fundId: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await client.post('/import/nav', formData, {
    params: { fund_id: fundId },
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

// Benchmarks
export async function fetchBenchmarks() {
  const { data } = await client.get<PaginatedResponse<any>>('/benchmarks');
  return data;
}

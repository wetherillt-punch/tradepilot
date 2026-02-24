// src/utils/api.ts
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://fearless-achievement-production.up.railway.app/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('providerToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ============================================================================
// PROVIDERS API
// ============================================================================

export const providersAPI = {
  getById: (id: string) => api.get(`/providers/${id}`),
  update: (id: string, data: any) => api.put(`/providers/${id}`, data),
  updateStatus: (id: string, status: string) => api.patch(`/providers/${id}/status`, { status }),
};

// ============================================================================
// BOOKINGS API
// ============================================================================

export const bookingsAPI = {
  // Get provider's pending booking requests
  getPending: async (providerId: string) => {
    const response = await api.get(`/bookings/provider/${providerId}/pending`);
    return response.data;
  },

  // Get all provider bookings with filters
  getAll: async (providerId: string, params: {
    status?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
    skip?: number;
  } = {}) => {
    const queryParams = new URLSearchParams();
    if (params.status) queryParams.append('status', params.status);
    if (params.startDate) queryParams.append('startDate', params.startDate);
    if (params.endDate) queryParams.append('endDate', params.endDate);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.skip) queryParams.append('skip', params.skip.toString());
    
    const query = queryParams.toString();
    const response = await api.get(`/bookings/provider/${providerId}${query ? '?' + query : ''}`);
    return response.data;
  },

  // Get single booking
  getById: async (bookingId: string) => {
    const response = await api.get(`/bookings/${bookingId}`);
    return response.data;
  },

  // Provider confirms booking
  confirm: async (bookingId: string, providerId: string) => {
    const response = await api.post(`/bookings/${bookingId}/confirm`, {}, {
      headers: { 'x-provider-id': providerId }
    });
    return response.data;
  },

  // Provider declines booking
  decline: async (bookingId: string, providerId: string, reason: string) => {
    const response = await api.post(`/bookings/${bookingId}/decline`, { reason }, {
      headers: { 'x-provider-id': providerId }
    });
    return response.data;
  },

  // Provider proposes reschedule
  reschedule: async (bookingId: string, providerId: string, proposedStart: string, message?: string) => {
    const response = await api.post(`/bookings/${bookingId}/reschedule`, {
      proposedStart,
      message
    }, {
      headers: { 'x-provider-id': providerId }
    });
    return response.data;
  },

  // Get booking history/audit trail
  getHistory: async (bookingId: string) => {
    const response = await api.get(`/bookings/${bookingId}/history`);
    return response.data;
  }
};

// ============================================================================
// AUTH API
// ============================================================================

export const authAPI = {
  login: (email: string, password: string) => api.post('/auth/provider/login', { email, password }),
  logout: () => {
    localStorage.removeItem('providerToken');
    localStorage.removeItem('providerId');
  },
};

export default api;

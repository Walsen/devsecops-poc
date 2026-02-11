import axios from 'axios';
import type { CertificationSubmission, SubmissionResponse } from '../types/certification';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Security: Include cookies in requests for httpOnly token auth
  withCredentials: true,
});

// Security: CSRF token handling for state-changing requests
api.interceptors.request.use((config) => {
  // Get CSRF token from cookie (set by server)
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrf_token='))
    ?.split('=')[1];
  
  if (csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(config.method?.toUpperCase() || '')) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  
  return config;
});

// Handle 401 responses (session expired)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Session expired - redirect to login or refresh token
      console.warn('Session expired, redirecting to login...');
      // window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/**
 * Set authentication session after Cognito login.
 * 
 * Security: Stores tokens in httpOnly cookies on the server,
 * protecting them from XSS attacks.
 */
export async function setAuthSession(accessToken: string, refreshToken?: string): Promise<void> {
  await api.post('/api/v1/auth/session', {
    access_token: accessToken,
    refresh_token: refreshToken,
  });
}

/**
 * Logout and clear session.
 */
export async function logout(): Promise<void> {
  await api.post('/api/v1/auth/logout');
}

/**
 * Check if user has an active session.
 */
export async function checkSession(): Promise<boolean> {
  try {
    const { data } = await api.get('/api/v1/auth/session');
    return data.success;
  } catch {
    return false;
  }
}

export async function submitCertification(
  submission: CertificationSubmission
): Promise<SubmissionResponse> {
  const { data } = await api.post<SubmissionResponse>('/api/v1/certifications', {
    member_name: submission.memberName,
    certification_type: submission.certificationType,
    certification_date: submission.certificationDate,
    photo_url: submission.photoUrl,
    linkedin_url: submission.linkedinUrl,
    personal_message: submission.personalMessage,
    channels: submission.channels,
  });
  return data;
}

export async function getSubmissionStatus(id: string): Promise<SubmissionResponse> {
  const { data } = await api.get<SubmissionResponse>(`/api/v1/certifications/${id}`);
  return data;
}

export default api;

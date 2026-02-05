import axios from 'axios';
import type { CertificationSubmission, SubmissionResponse } from '../types/certification';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

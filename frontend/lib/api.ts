import axios from 'axios';

const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({ baseURL });

api.interceptors.request.use((c) => {
  if (typeof window !== 'undefined') {
    const t = localStorage.getItem('token');
    if (t) c.headers.Authorization = `Bearer ${t}`;
  }
  return c;
});

export function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  window.location.href = '/login';
}

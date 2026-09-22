import axios from 'axios';

const TOKEN_KEY = 'ualflix-admin-token';

export const api = axios.create({ baseURL: '/api' });

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

let handleUnauthorized = () => {};

// Lets the app drop back to the login screen when a token expires mid-session.
export function onUnauthorized(handler) {
  handleUnauthorized = handler;
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLogin = error.config?.url === '/auth/login';
    if (error.response?.status === 401 && !isLogin) {
      clearToken();
      handleUnauthorized();
    }
    return Promise.reject(error);
  }
);

export async function login(username, password) {
  const form = new URLSearchParams({ username, password });
  const { data } = await api.post('/auth/login', form);
  localStorage.setItem(TOKEN_KEY, data.access_token);
  const { data: user } = await api.get('/auth/me');
  return user;
}

// Calls `onChange` whenever the catalog changes (including processing progress),
// and after a dropped connection comes back. Returns a function that closes it.
export function subscribeToCatalog(onChange) {
  const source = new EventSource('/api/events');
  let connectedBefore = false;
  source.onopen = () => {
    if (connectedBefore) onChange();
    connectedBefore = true;
  };
  source.onmessage = () => onChange();
  return () => source.close();
}

export function errorMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

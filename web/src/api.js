import axios from 'axios';

// Everything is served from the same origin through nginx, so relative URLs work
// both in the container setup and with `npm start` (see "proxy" in package.json).
export const api = axios.create({ baseURL: '/api' });

// Calls `onChange` with each catalog change pushed by the server, shaped
// `{ action, video_id }`. After a dropped connection comes back it's called with
// `{ action: 'resync' }`, since changes may have been missed in between.
// Returns a function that closes the connection.
export function subscribeToCatalog(onChange) {
  const source = new EventSource('/api/events');
  let connectedBefore = false;
  source.onopen = () => {
    if (connectedBefore) onChange({ action: 'resync' });
    connectedBefore = true;
  };
  source.onmessage = (message) => onChange(JSON.parse(message.data));
  return () => source.close();
}

export function errorMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

export function formatDuration(seconds) {
  if (!seconds || seconds <= 0) {
    return '--:--';
  }
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = String(total % 60).padStart(2, '0');
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${secs}`
    : `${minutes}:${secs}`;
}

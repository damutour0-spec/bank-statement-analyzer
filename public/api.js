const DEFAULT_API_BASE_URL = ["https://bank-statement-api-w71k", "onrender", "com"].join(".");
const API_BASE_URL = (window.APP_CONFIG && window.APP_CONFIG.apiBaseUrl) || DEFAULT_API_BASE_URL;

function apiUrl(path) {
  if (!path) {
    return API_BASE_URL;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

function apiFetch(path, options) {
  return fetch(apiUrl(path), options);
}

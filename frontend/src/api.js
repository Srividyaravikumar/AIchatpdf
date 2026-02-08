// src/api.js
export function getApiBase() {
  const base = process.env.REACT_APP_API_BASE;
  if (!base) {
    // This is a fallback so your app doesn't crash during local development
    return "http://localhost:5000"; 
  }
  return base.replace(/\/$/, "");
}

export const API_BASE = getApiBase();
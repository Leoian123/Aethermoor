/**
 * STATISFY RPG - Auth Utilities
 * Token management e auth guards per pagine Astro statiche.
 */

const TOKEN_KEY = 'statisfy_token';
const USER_KEY = 'statisfy_user';

/** Salva token e dati utente dopo login/register */
export function saveAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** Legge il token salvato */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/** Legge i dati utente salvati */
export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Rimuove tutti i dati auth */
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/** Controlla se l'utente e' autenticato (token presente e non scaduto) */
export function isAuthenticated() {
  const token = getToken();
  if (!token) return false;

  try {
    // Decode JWT payload (base64) per controllare scadenza client-side
    const payload = JSON.parse(atob(token.split('.')[1]));
    const now = Math.floor(Date.now() / 1000);
    return payload.exp > now;
  } catch {
    return false;
  }
}

/**
 * Auth guard — da chiamare come prima riga nello script di ogni pagina protetta.
 * Se non autenticato, redirect a /login.
 */
export function requireAuth() {
  if (!isAuthenticated()) {
    clearAuth();
    window.location.href = '/login';
    return false;
  }
  return true;
}

/**
 * Redirect guard — da chiamare nella pagina di login.
 * Se gia' autenticato, redirect a /home.
 */
export function redirectIfAuthenticated() {
  if (isAuthenticated()) {
    window.location.href = '/home';
    return true;
  }
  return false;
}

/** Logout: cancella dati e redirect a /login */
export function logout() {
  clearAuth();
  window.location.href = '/login';
}

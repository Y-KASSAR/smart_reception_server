import axios, { AxiosError } from "axios";

const TOKEN_KEY = "sra_jwt_token";
const ROLE_KEY = "sra_role";
const USERNAME_KEY = "sra_username";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, role: string, username: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
  localStorage.setItem(USERNAME_KEY, username);
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USERNAME_KEY);
}

export function currentRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}

export function currentUsername(): string | null {
  return localStorage.getItem(USERNAME_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// Base URL is "" because Vite dev-server proxies /api → :5000.
// In production the SPA is served by FastAPI on the same origin.
export const api = axios.create({
  baseURL: "",
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError<any>) => {
    if (err.response?.status === 401) {
      clearAuth();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    } else if (err.response?.status === 403) {
      // Permission denied — surface via toast so callers don't need to wire
      // their own alert() handlers. Avoid duplicates by deferring to module.
      import("../components/Toast/Toast").then(({ toast }) => {
        toast.error("Permission denied", err.response?.data?.detail ?? "Admin role required.");
      });
    } else if (err.response && err.response.status >= 500) {
      import("../components/Toast/Toast").then(({ toast }) => {
        toast.error("Server error", err.response?.data?.detail ?? "Something failed on the backend.");
      });
    }
    return Promise.reject(err);
  }
);

// -------- typed endpoint wrappers (small surface, expand as we add pages) --

export async function login(username: string, password: string) {
  const { data } = await api.post("/api/staff/login", { username, password });
  return data as {
    access_token: string;
    token_type: string;
    staff: { id: number; username: string; role: string; full_name: string };
  };
}

export async function logout() {
  clearAuth();
}

export interface SubsystemStatus {
  name: string;
  ok: boolean;
  detail: string;
}

export interface SystemStatus {
  server_uptime_seconds: number;
  timestamp: string;
  database: SubsystemStatus;
  recognition: SubsystemStatus;
  person_detection: SubsystemStatus;
  monitoring: SubsystemStatus;
  alert_pipeline: SubsystemStatus;
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const { data } = await api.get<SystemStatus>("/api/system/status");
  return data;
}

export interface Alert {
  id: number;
  alert_type: string;
  status: string;
  title: string;
  description: string | null;
  severity: number;
  location: string | null;
  guest_id: number | null;
  acknowledged_by: string | null;
  created_at: string;
}

export async function fetchAlerts(status?: string): Promise<Alert[]> {
  const url = status ? `/api/alerts/?status=${status}` : "/api/alerts/";
  const { data } = await api.get<Alert[]>(url);
  return data;
}

export async function fetchPendingAlerts(): Promise<Alert[]> {
  const { data } = await api.get<Alert[]>("/api/alerts/pending");
  return data;
}

export async function acknowledgeAlert(alertId: number, staffId: number) {
  await api.post(`/api/alerts/${alertId}/acknowledge?staff_id=${staffId}`);
}

export async function resolveAlert(alertId: number) {
  await api.post(`/api/alerts/${alertId}/resolve`);
}

export interface Guest {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  nationality: string | null;
  id_type?: string | null;
  id_number?: string | null;
  language_preference?: string;
  vip_status: boolean;
  status: string;
  preferences: string | null;
  notes: string | null;
  is_watched?: boolean;
  watch_reason?: string | null;
  is_staff_badge?: boolean;
  staff_badge_label?: string | null;
  created_at: string;
}

export async function fetchGuest(guestId: number): Promise<Guest> {
  const { data } = await api.get<Guest>(`/api/guests/${guestId}`);
  return data;
}

export interface GuestSummary {
  guest: Guest;
  stays: {
    total: number;
    completed: number;
    active: number;
    items: Array<{
      id: number;
      reservation_code: string;
      room_number: string | null;
      check_in_date: string | null;
      check_out_date: string | null;
      status: string | null;
      total_amount: number | null;
      special_requests: string | null;
    }>;
  };
  visits: {
    total: number;
    items: Array<{
      id: number;
      entry_time: string | null;
      exit_time: string | null;
      duration_seconds: number | null;
    }>;
  };
  recommendations: {
    total: number;
    accepted: number;
    declined: number;
    items: Array<{
      id: number;
      score: number;
      status: string | null;
      reasoning: string | null;
      created_at: string | null;
      service: { id: number; name: string; category: string; price: number | null } | null;
    }>;
  };
  finance: {
    total_billed: number;
    avg_per_stay: number;
    accepted_services_value: number;
    currency: string;
  };
  special_requests_history: string[];
}

export async function fetchGuestSummary(guestId: number): Promise<GuestSummary> {
  const { data } = await api.get<GuestSummary>(`/api/guests/${guestId}/summary`);
  return data;
}

export async function searchGuests(query: string): Promise<Guest[]> {
  // Backend matches name, email, phone, and ID number — pass it as `q`.
  const { data } = await api.get<Guest[]>(`/api/guests/search?q=${encodeURIComponent(query)}`);
  return data;
}

// ----- Reservations (dashboard tabs) -----

export interface Reservation {
  id: number;
  guest_id: number;
  reservation_code: string;
  check_in_date: string;
  check_out_date: string;
  room_type: string | null;
  room_number: string | null;
  num_guests: number;
  status: string;
  rate_per_night: number | null;
  total_amount: number | null;
  special_requests: string | null;
  guest?: Guest | null;
}

export async function fetchInHouseReservations(): Promise<Reservation[]> {
  const { data } = await api.get<Reservation[]>("/api/reservations/in-house");
  return data;
}

export async function fetchArrivals(days = 1): Promise<Reservation[]> {
  const { data } = await api.get<Reservation[]>(`/api/reservations/arrivals?days=${days}`);
  return data;
}

export async function fetchDepartures(days = 1): Promise<Reservation[]> {
  const { data } = await api.get<Reservation[]>(`/api/reservations/departures?days=${days}`);
  return data;
}

// ----- Watchlist -----

export async function fetchWatchlist(): Promise<Guest[]> {
  const { data } = await api.get<Guest[]>("/api/guests/watchlist");
  return data;
}

export async function setGuestWatchlist(
  guestId: number,
  isWatched: boolean,
  reason?: string
): Promise<Guest> {
  const { data } = await api.put<Guest>(`/api/guests/${guestId}/watch`, {
    is_watched: isWatched,
    watch_reason: reason ?? null,
  });
  return data;
}

export async function setStaffBadge(
  guestId: number,
  isStaff: boolean,
  label?: string
): Promise<Guest> {
  const { data } = await api.put<Guest>(`/api/guests/${guestId}/staff-badge`, {
    is_staff_badge: isStaff,
    staff_badge_label: label ?? null,
  });
  return data;
}

// Add a face embedding to an EXISTING guest (used when a passport-only
// profile arrives at the lobby and we want to attach a face to it).
export interface EmbedResult {
  guest_id: number;
  embeddings_total: number;
  status: string;
}

export async function embedFaceForGuest(guestId: number, frameB64: string): Promise<EmbedResult> {
  const { data } = await api.post<EmbedResult>(`/api/guests/${guestId}/embed`, { frame_b64: frameB64 });
  return data;
}

export interface ServiceSummary {
  id: number;
  name: string;
  category: string;
  description: string | null;
  price: number | null;
  is_active: boolean;
  popularity_score: number;
}

export interface Recommendation {
  id: number;
  guest_id: number;
  service_id: number;
  score: number;
  reasoning: string | null;
  status: string;
  service?: ServiceSummary | null;
}

export async function fetchRecommendations(guestId: number): Promise<Recommendation[]> {
  const { data } = await api.get<Recommendation[]>(`/api/recommendations/guest/${guestId}`);
  return data;
}

export async function generateRecommendations(guestId: number, limit = 5): Promise<Recommendation[]> {
  const { data } = await api.post<Recommendation[]>(
    `/api/recommendations/generate/${guestId}?limit=${limit}`
  );
  return data;
}

// FR-2.8 — staff marks a recommendation as accepted / declined / presented
// (the SDD's "deferred" maps to "presented" in our enum: the staff acknowledged
// it but the guest hasn't responded yet).
export type RecommendationActionStatus = "accepted" | "declined" | "presented";

export async function setRecommendationStatus(
  recId: number,
  status: RecommendationActionStatus,
): Promise<Recommendation> {
  const { data } = await api.put<Recommendation>(
    `/api/recommendations/${recId}/status`,
    status,                              // backend expects raw enum value in body
    { headers: { "Content-Type": "application/json" } },
  );
  return data;
}

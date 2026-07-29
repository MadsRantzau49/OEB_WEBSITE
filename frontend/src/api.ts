const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

let csrfToken = "";

const errorMessages: Record<string, string> = {
  authentication_required: "Du skal logge ind først.",
  csrf_failed: "Din session er udløbet. Genindlæs siden og prøv igen.",
  invalid_username_or_password: "Brugernavn eller adgangskode er forkert.",
  username_already_exists: "Brugernavnet er allerede taget.",
  player_already_has_account: "Spilleren har allerede en bruger.",
  player_already_exists: "Spilleren findes allerede.",
  player_account_not_found: "Spilleren har ikke et brugerlogin.",
  dbu_matches_are_managed_by_dbu: "DBU-kampe kan ikke slettes manuelt.",
  owner_account_cannot_be_deleted: "Ejerkontoen kan ikke slettes.",
  select_at_least_one_valid_player: "Vælg mindst én spiller.",
  fine_rule_not_found: "Vælg en gyldig bøde.",
  fine_charge_not_found: "Bøden findes ikke længere.",
  permission_denied: "Du har ikke rettighed til denne handling.",
  internal_server_error: "Der opstod en teknisk fejl. Prøv igen.",
};

export function setCsrfToken(token: string) {
  csrfToken = token;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const isFormData = options.body instanceof FormData;
  if (!isFormData && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken && options.method && options.method !== "GET") {
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(errorMessages[payload.error] || payload.error || "Der skete en fejl. Prøv igen.");
  }
  return payload as T;
}

export function jsonBody(value: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(value) };
}

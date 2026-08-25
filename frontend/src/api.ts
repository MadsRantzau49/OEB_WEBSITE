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
  minutes_late_must_be_positive_integer: "Angiv antal minutter for sent som et positivt heltal.",
  permission_denied: "Du har ikke rettighed til denne handling.",
  mobilepay_drive_not_configured: "Google Drive er ikke konfigureret på serveren.",
  mobilepay_drive_not_configured_for_squad: "Google Drive-mappen er ikke knyttet til dette hold.",
  mobilepay_drive_access_denied: "Serveren har ikke adgang til Google Drive-mappen.",
  mobilepay_drive_folder_not_found: "Google Drive-mappen blev ikke fundet. Kontrollér mappe-id'et, og del mappen med servicekontoen.",
  mobilepay_drive_file_not_found: "Der blev ikke fundet nogen MobilePay Excel-fil i Google Drive-mappen.",
  mobilepay_drive_unavailable: "Google Drive kunne ikke kontaktes. Prøv igen.",
  mobilepay_drive_import_in_progress: "En anden Google Drive-import er allerede i gang.",
  mobilepay_import_failed: "MobilePay-filen kunne ikke importeres. Prøv igen.",
  file_too_large: "Excel-filen er større end 10 MB.",
  internal_server_error: "Der opstod en teknisk fejl. Prøv igen.",
};

export function apiErrorMessage(code: string) {
  return errorMessages[code] || code || "Der skete en fejl. Prøv igen.";
}

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
    throw new Error(apiErrorMessage(payload.error));
  }
  return payload as T;
}

export function jsonBody(value: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(value) };
}

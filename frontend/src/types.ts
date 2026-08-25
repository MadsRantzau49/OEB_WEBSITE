export type Permission =
  | "approve_fine_requests"
  | "issue_fines"
  | "manage_fine_rules"
  | "manage_finance"
  | "manage_roster"
  | "manage_matches"
  | "manage_dbu_sync"
  | "manage_permissions";

export interface User {
  id: number;
  username: string;
  isOwner: boolean;
  playerId: number | null;
  playerSquadId: number | null;
  permissions: { squadId: number; permission: Permission }[];
}

export interface Season {
  id: number;
  squadId: number;
  name: string;
  dbuUrl: string | null;
  startDate: string;
  endDate: string | null;
  active: boolean;
}

export interface Squad {
  id: number;
  name: string;
  slug: string;
  dbuClubName: string;
  dbuSeasonUrl: string | null;
  currentSeason: Season | null;
}

export interface Charge {
  id: number;
  playerId: number;
  playerName?: string | null;
  seasonId: number;
  matchId: number | null;
  source: string;
  title: string;
  description: string;
  amount: number;
  date: string;
}

export interface Transaction {
  id: number;
  date: string;
  name: string | null;
  type: string | null;
  number: string | null;
  message: string | null;
  amount: number;
  currency: string | null;
  transactionType: string;
  allocationStatus: string;
  allocatedPlayerId: number | null;
  allocatedPlayerName: string | null;
}

export interface Player {
  id: number;
  squadId: number;
  name: string;
  dbuName: string;
  mobilePayName: string | null;
  active: boolean;
  hasAccount?: boolean;
  totalFines: number;
  totalPaid: number;
  balance: number;
  washes: number;
  fines: Charge[];
  payments: Transaction[];
}

export interface Rule {
  id: number;
  name: string;
  description: string;
  amount: number;
  amountCents: number;
  type: string;
  active: boolean;
}

export interface Participant {
  id: number | null;
  name: string;
  playerId: number | null;
  playerName: string | null;
  status: string;
}

export interface Match {
  id: number;
  dbuId: string | null;
  date: string | null;
  homeClub: string | null;
  awayClub: string | null;
  homeScore: number | null;
  awayScore: number | null;
  status: string;
  syncError: string | null;
  lastSyncedAt: string | null;
  washerId: number | null;
  washerName: string | null;
  lineupLocked: boolean;
  participants: Participant[];
}

export interface BalanceSummary {
  boxBalance: number;
  ifEveryonePays: number;
  outstanding: number;
  playerCredit: number;
  totalFines: number;
  totalPaid: number;
  debtors: number;
}

export interface PaymentSettings {
  boxNumber: string | null;
  paymentUrl: string | null;
}

export interface DbuSource {
  id: number;
  label: string;
  url: string;
}

export interface MobilePayGoogleDriveIntegration {
  configured: boolean;
  automatic: boolean;
  pollIntervalSeconds: number;
  workerStatus: "disabled" | "waiting" | "running" | "stale";
  serviceAccountEmail: string | null;
  lastCheckedAt: string | null;
  lastSuccessAt: string | null;
  lastError: string | null;
  latestFilename: string | null;
  latestModifiedTime: string | null;
}

export interface Dashboard {
  squad: Squad;
  season: Season;
  seasons: Season[];
  players: Player[];
  matches: Match[];
  rules: Rule[];
  expenses: Transaction[];
  balanceSummary: BalanceSummary;
  payment: PaymentSettings;
  dbuSources: DbuSource[];
  lastSync: string | null;
  integrations?: { mobilePayGoogleDrive: MobilePayGoogleDriveIntegration };
}

export interface FineRequest {
  id: number;
  squadId: number;
  seasonId: number;
  ruleId: number | null;
  title: string;
  description: string;
  amount: number;
  status: "pending" | "approved" | "rejected";
  reviewNote: string | null;
  requester: string;
  reviewer: string | null;
  recipients: { id: number; name: string }[];
  createdAt: string;
  reviewedAt: string | null;
}

export interface PermissionUser {
  id: number;
  username: string;
  playerId: number | null;
  isOwner: boolean;
  permissions: Permission[];
}

export interface SetupStatus {
  needsSetup: boolean;
  clubName: string | null;
  squads: Squad[];
}

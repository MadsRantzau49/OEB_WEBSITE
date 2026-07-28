import { type ChangeEvent, type FormEvent, type ReactNode, useEffect, useState } from "react";
import { api, jsonBody } from "./api";
import type { Dashboard, FineRequest, Match, Permission, PermissionUser, Transaction, User } from "./types";

const permissionLabels: Record<Permission, string> = {
  approve_fine_requests: "Godkend anmodninger",
  issue_fines: "Giv bøder",
  manage_fine_rules: "Bødetakster",
  manage_finance: "MobilePay",
  manage_roster: "Spillere",
  manage_matches: "Kampe og vasker",
  manage_dbu_sync: "DBU-opdatering",
  manage_permissions: "Rettigheder",
};
const permissionKeys = Object.keys(permissionLabels) as Permission[];

function can(user: User, squadId: number, permission: Permission) {
  return user.isOwner || user.permissions.some((item) => item.squadId === squadId && item.permission === permission);
}

function money(value: number) {
  return `${new Intl.NumberFormat("da-DK", { maximumFractionDigits: 2 }).format(value)} kr.`;
}

function dateLabel(value: string | null) {
  if (!value) return "Dato mangler";
  return new Intl.DateTimeFormat("da-DK", { dateStyle: "short" }).format(new Date(value));
}

export default function AdminPanel({ dashboard, user, onFailure, onRefresh }: { dashboard: Dashboard; user: User; onFailure: (reason: unknown) => void; onRefresh: () => void }) {
  const squadId = dashboard.squad.id;
  const allowed = (permission: Permission) => can(user, squadId, permission);
  const [requests, setRequests] = useState<FineRequest[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);

  async function loadTasks() {
    if (allowed("approve_fine_requests")) {
      try { setRequests((await api<{ requests: FineRequest[] }>(`/squads/${squadId}/fine-requests`)).requests); }
      catch (reason) { onFailure(reason); }
    }
    if (allowed("manage_finance")) {
      try { setTransactions((await api<{ transactions: Transaction[] }>(`/squads/${squadId}/transactions?seasonId=${dashboard.season.id}`)).transactions); }
      catch (reason) { onFailure(reason); }
    }
  }

  useEffect(() => { void loadTasks(); }, [squadId, dashboard.season.id, dashboard.season.startDate, dashboard.season.endDate]);

  const hasAdminTools = user.isOwner || permissionKeys.some(
    (permission) => permission !== "issue_fines" && allowed(permission),
  );

  async function review(requestId: number, action: "approve" | "reject") {
    try {
      await api(`/squads/${squadId}/fine-requests/${requestId}/${action}`, jsonBody({}));
      await loadTasks(); onRefresh();
    } catch (reason) { onFailure(reason); }
  }

  if (!hasAdminTools) return null;

  return (
    <details className="admin-fold">
      <summary>Administration</summary>
      <div className="admin-tools">
        <Reminder dashboard={dashboard} />
        {allowed("approve_fine_requests") && <Tool title={`Anmodninger (${requests.filter((item) => item.status === "pending").length})`}><RequestReview requests={requests} onReview={review} /></Tool>}
        {allowed("manage_finance") && <Tool title="MobilePay"><FinanceTool dashboard={dashboard} transactions={transactions} onError={onFailure} onSaved={async () => { await loadTasks(); onRefresh(); }} /></Tool>}
        {allowed("manage_roster") && <Tool title="Spillere"><RosterTool dashboard={dashboard} onError={onFailure} onSaved={onRefresh} /></Tool>}
        {allowed("manage_matches") && <Tool title="Kampe, spillere og vasker"><MatchTool dashboard={dashboard} onError={onFailure} onSaved={onRefresh} /></Tool>}
        {allowed("manage_dbu_sync") && <Tool title="DBU-links"><DbuTool dashboard={dashboard} onError={onFailure} onSaved={onRefresh} /></Tool>}
        {allowed("manage_fine_rules") && <Tool title="Bødetakster"><RuleTool dashboard={dashboard} onError={onFailure} onSaved={onRefresh} /></Tool>}
        {allowed("manage_permissions") && <Tool title="Brugerrettigheder"><PermissionTool squadId={squadId} onError={onFailure} /></Tool>}
        {user.isOwner && <Tool title="Nyt hold"><NewSquad onError={onFailure} /></Tool>}
      </div>
    </details>
  );
}

function Reminder({ dashboard }: { dashboard: Dashboard }) {
  const [copied, setCopied] = useState(false);
  const debtors = dashboard.players.filter((player) => player.balance < 0);
  const lines = [
    `Bødekassen · ${dashboard.squad.name}`,
    dashboard.payment.boxNumber ? `MobilePay Box: ${dashboard.payment.boxNumber}` : "",
    "",
    ...debtors.map((player) => `${player.name}: ${money(-player.balance)}`),
    "",
    `Se hvorfor og betal her: ${window.location.href}`,
  ].filter((line, index, all) => line !== "" || all[index - 1] !== "");
  const text = debtors.length ? lines.join("\n") : `Alle har betalt i ${dashboard.squad.name}.`;
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
  }
  return <section className="reminder-box"><b>Messenger-påmindelse</b><textarea readOnly rows={Math.min(Math.max(debtors.length + 5, 5), 14)} value={text} /><button className="save-button" onClick={() => void copy()}>{copied ? "Kopieret" : "Kopiér tekst"}</button></section>;
}

function Tool({ title, children }: { title: string; children: ReactNode }) {
  return <details className="tool"><summary>{title}</summary><div className="tool-content">{children}</div></details>;
}

function RequestReview({ requests, onReview }: { requests: FineRequest[]; onReview: (id: number, action: "approve" | "reject") => void }) {
  const pending = requests.filter((item) => item.status === "pending");
  if (!pending.length) return <p className="empty-copy">Ingen anmodninger.</p>;
  return <div className="admin-rows">{pending.map((item) => <article key={item.id}><div><b>{item.title} · {money(item.amount)}</b><small>{item.recipients.map((recipient) => recipient.name).join(", ")} · fra {item.requester}</small></div><div className="mini-actions"><button onClick={() => onReview(item.id, "approve")}>Godkend</button><button onClick={() => onReview(item.id, "reject")}>Afvis</button></div></article>)}</div>;
}

function FinanceTool({ dashboard, transactions, onError, onSaved }: { dashboard: Dashboard; transactions: Transaction[]; onError: (reason: unknown) => void; onSaved: () => Promise<void> }) {
  const [boxNumber, setBoxNumber] = useState(dashboard.payment.boxNumber || "");
  const [paymentUrl, setPaymentUrl] = useState(dashboard.payment.paymentUrl || "");
  const [assignments, setAssignments] = useState<Record<number, string>>({});
  const [filters, setFilters] = useState({ expenses: true, assigned: true, unassigned: true });
  const [rematching, setRematching] = useState(false);
  const [rematchMessage, setRematchMessage] = useState("");
  async function saveSettings(event: FormEvent) {
    event.preventDefault();
    try { await api(`/squads/${dashboard.squad.id}/payment-settings`, { method: "PUT", body: JSON.stringify({ boxNumber, paymentUrl }) }); await onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file) return;
    const form = new FormData(); form.append("file", file);
    try { await api(`/squads/${dashboard.squad.id}/mobilepay-imports`, { method: "POST", body: form }); await onSaved(); }
    catch (reason) { onError(reason); }
    event.target.value = "";
  }
  async function assign(transactionId: number) {
    try { await api(`/squads/${dashboard.squad.id}/transactions/${transactionId}/assign`, jsonBody({ playerId: Number(assignments[transactionId]) })); await onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function remove(transactionId: number) {
    try { await api(`/squads/${dashboard.squad.id}/transactions/${transactionId}`, { method: "DELETE" }); await onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function rematch() {
    setRematching(true); setRematchMessage("");
    try {
      const result = await api<{ report: { checked: number; matched: number } }>(`/squads/${dashboard.squad.id}/transactions/rematch`, jsonBody({}));
      setRematchMessage(`${result.report.checked} rækker tjekket · ${result.report.matched} nye matches`);
      await onSaved();
    } catch (reason) { onError(reason); }
    finally { setRematching(false); }
  }
  const counts = {
    expenses: transactions.filter((item) => item.amount < 0).length,
    assigned: transactions.filter((item) => item.amount >= 0 && item.allocatedPlayerId).length,
    unassigned: transactions.filter((item) => item.amount >= 0 && !item.allocatedPlayerId).length,
  };
  const visibleTransactions = transactions.filter((item) => item.amount < 0 ? filters.expenses : item.allocatedPlayerId ? filters.assigned : filters.unassigned);
  function toggleFilter(key: "expenses" | "assigned" | "unassigned") {
    setFilters((current) => ({ ...current, [key]: !current[key] }));
  }
  return <><SeasonSettings dashboard={dashboard} onError={onError} onSaved={() => void onSaved()} /><form onSubmit={saveSettings}><Field label="Box-nummer" hint="Fx 1783QN" value={boxNumber} onChange={setBoxNumber} /><Field label="Delelink fra MobilePay Box" hint="Del → kopiér link" value={paymentUrl} onChange={setPaymentUrl} /><button className="save-button">Gem betalingslink</button></form><label className="upload"><input type="file" accept=".xlsx" onChange={upload} />Upload MobilePay Excel</label><button className="secondary-save" type="button" disabled={rematching} onClick={() => void rematch()}>{rematching ? "Tjekker…" : "Tjek spillernavne igen"}</button>{rematchMessage && <p className="save-confirmation">{rematchMessage}</p>}<div className="transaction-filter"><button type="button" aria-pressed={filters.expenses} onClick={() => toggleFilter("expenses")}>Negative beløb <span>{counts.expenses}</span></button><button type="button" aria-pressed={filters.assigned} onClick={() => toggleFilter("assigned")}>Tildelt <span>{counts.assigned}</span></button><button type="button" aria-pressed={filters.unassigned} onClick={() => toggleFilter("unassigned")}>Mangler spiller <span>{counts.unassigned}</span></button></div><p className="transaction-count">Viser {visibleTransactions.length} af {transactions.length} rækker fra den valgte periode.</p>{visibleTransactions.length > 0 ? <div className="admin-rows transaction-list"><h4>MobilePay-rækker</h4>{visibleTransactions.map((item) => <article key={item.id}><div><b>{dateLabel(item.date)} · {item.name || "Ukendt"}</b><small>{item.transactionType === "pay_out" ? "Udgift" : item.allocatedPlayerName ? `Tildelt ${item.allocatedPlayerName}` : "Mangler spiller"} · {item.message || "Ingen besked"}</small><strong>{money(item.amount)}</strong></div><div className="transaction-actions">{item.transactionType === "pay_in" && !item.allocatedPlayerId && <div className="assign-row"><select value={assignments[item.id] || ""} onChange={(event) => setAssignments({ ...assignments, [item.id]: event.target.value })}><option value="">Vælg spiller</option>{dashboard.players.map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}</select><button disabled={!assignments[item.id]} onClick={() => void assign(item.id)}>Tildel</button></div>}<button className="text-danger" onClick={() => void remove(item.id)}>Fjern</button></div></article>)}</div> : <p className="empty-copy">Ingen MobilePay-rækker matcher de valgte filtre og datoer.</p>}</>;
}

function RosterTool({ dashboard, onError, onSaved }: { dashboard: Dashboard; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [dbuName, setDbuName] = useState("");
  const [mobilePayName, setMobilePayName] = useState("");
  const [search, setSearch] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await api(`/squads/${dashboard.squad.id}/players`, jsonBody({ dbuName, mobilePayName })); setDbuName(""); setMobilePayName(""); onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function addSuggested(name: string) {
    try { await api(`/squads/${dashboard.squad.id}/players`, jsonBody({ dbuName: name, mobilePayName: name })); onSaved(); }
    catch (reason) { onError(reason); }
  }
  const suggestions = Array.from(new Set(dashboard.matches.flatMap((match) => match.participants.filter((item) => item.status === "unmatched").map((item) => item.name)))).sort();
  const visiblePlayers = dashboard.players.filter((player) => player.name.toLocaleLowerCase("da-DK").includes(search.trim().toLocaleLowerCase("da-DK")));
  return <><form onSubmit={submit}><Field label="Navn præcis som på DBU" value={dbuName} onChange={setDbuName} required /><Field label="Navn i MobilePay" value={mobilePayName} onChange={setMobilePayName} /><button className="save-button">Tilføj spiller manuelt</button></form>{suggestions.length > 0 && <div className="suggestions"><b>Ikke oprettet endnu</b><p>DBU-navnene får først bøder, når du tilføjer dem.</p>{suggestions.map((name) => <button key={name} type="button" onClick={() => void addSuggested(name)}>{name}<span>+</span></button>)}</div>}<div className="player-management"><Field label={`${dashboard.players.length} spillere`} hint="Søg for at redigere eller slette" value={search} onChange={setSearch} />{visiblePlayers.map((player) => <PlayerEditor key={`${player.id}-${player.dbuName}-${player.mobilePayName}`} player={player} squadId={dashboard.squad.id} onError={onError} onSaved={onSaved} />)}{visiblePlayers.length === 0 && <p className="empty-copy">Ingen spillere matcher.</p>}</div></>;
}

function PlayerEditor({ player, squadId, onError, onSaved }: { player: Dashboard["players"][number]; squadId: number; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [dbuName, setDbuName] = useState(player.dbuName);
  const [mobilePayName, setMobilePayName] = useState(player.mobilePayName || "");
  async function save(event: FormEvent) {
    event.preventDefault();
    try { await api(`/squads/${squadId}/players/${player.id}`, { method: "PATCH", body: JSON.stringify({ dbuName, mobilePayName }) }); onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function remove() {
    if (!window.confirm(`Slet ${player.name}? Spilleren kan kun slettes uden bruger, betalinger eller almindelige bøder.`)) return;
    try { await api(`/squads/${squadId}/players/${player.id}`, { method: "DELETE" }); onSaved(); }
    catch (reason) { onError(reason); }
  }
  return <details className="player-editor"><summary><span>{player.name}<small>{player.mobilePayName || "Intet MobilePay-navn"}</small></span><b>{money(player.balance)}</b></summary><form onSubmit={save}><Field label="DBU-navn" value={dbuName} onChange={setDbuName} required /><Field label="MobilePay-navn" value={mobilePayName} onChange={setMobilePayName} /><button className="secondary-save">Gem spiller</button><button className="danger-button" type="button" onClick={() => void remove()}>Slet spiller</button></form></details>;
}

function MatchTool({ dashboard, onError, onSaved }: { dashboard: Dashboard; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [date, setDate] = useState("");
  const [homeClub, setHomeClub] = useState(dashboard.squad.dbuClubName);
  const [awayClub, setAwayClub] = useState("");
  const [homeScore, setHomeScore] = useState("");
  const [awayScore, setAwayScore] = useState("");
  useEffect(() => { setHomeClub(dashboard.squad.dbuClubName); }, [dashboard.squad.id]);
  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api(`/squads/${dashboard.squad.id}/matches`, jsonBody({ seasonId: dashboard.season.id, date, homeClub, awayClub, homeScore, awayScore }));
      setDate(""); setAwayClub(""); setHomeScore(""); setAwayScore(""); onSaved();
    } catch (reason) { onError(reason); }
  }
  return <><form className="manual-match-form" onSubmit={create}><b>Tilføj kamp uden DBU</b><p className="help-text">Brug denne til trænings- og venskabskampe.</p><Field label="Dato og tid" type="datetime-local" value={date} onChange={setDate} required /><div className="two-fields"><Field label="Hjemmehold" value={homeClub} onChange={setHomeClub} required /><Field label="Udehold" value={awayClub} onChange={setAwayClub} required /></div><div className="two-fields"><Field label="Hjemme mål" type="number" value={homeScore} onChange={setHomeScore} required /><Field label="Ude mål" type="number" value={awayScore} onChange={setAwayScore} required /></div><button className="save-button">Tilføj kamp</button></form>{!dashboard.matches.length ? <p className="empty-copy">Ingen kampe endnu.</p> : <div className="match-editors">{dashboard.matches.map((match) => <MatchEditor key={`${match.id}-${match.lineupLocked}-${match.washerId}-${match.participants.map((item) => item.playerId).join("-")}`} match={match} dashboard={dashboard} onError={onError} onSaved={onSaved} />)}</div>}</>;
}

function SeasonSettings({ dashboard, onError, onSaved }: { dashboard: Dashboard; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [startDate, setStartDate] = useState(dashboard.season.startDate);
  const [endDate, setEndDate] = useState(dashboard.season.endDate || "");
  const [saved, setSaved] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    try { await api(`/squads/${dashboard.squad.id}/seasons/${dashboard.season.id}`, { method: "PATCH", body: JSON.stringify({ startDate, endDate }) }); setSaved(true); onSaved(); }
    catch (reason) { onError(reason); }
  }
  return <form className="season-settings" onSubmit={save}><p className="help-text">Datoerne bestemmer hvilke MobilePay-rækker der tæller med.</p><div className="two-fields"><Field label="Fra" type="date" value={startDate} onChange={(value) => { setStartDate(value); setSaved(false); }} required /><Field label="Til" type="date" value={endDate} onChange={(value) => { setEndDate(value); setSaved(false); }} /></div><button className="secondary-save">Gem datoer</button>{saved && <p className="save-confirmation">Datoerne er gemt.</p>}</form>;
}

function MatchEditor({ match, dashboard, onError, onSaved }: { match: Match; dashboard: Dashboard; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [lineup, setLineup] = useState<number[]>(match.participants.flatMap((item) => item.playerId ? [item.playerId] : []));
  const [washer, setWasher] = useState(match.washerId ? String(match.washerId) : "");
  const [addPlayerId, setAddPlayerId] = useState("");
  async function saveLineup(playerIds: number[]) {
    try { await api(`/squads/${dashboard.squad.id}/matches/${match.id}/lineup`, { method: "PUT", body: JSON.stringify({ playerIds }) }); setLineup(playerIds); onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function resetLineup() {
    try { await api(`/squads/${dashboard.squad.id}/matches/${match.id}/lineup`, { method: "DELETE" }); onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function saveWasher(value: string) {
    setWasher(value);
    try { await api(`/squads/${dashboard.squad.id}/matches/${match.id}/washer`, { method: "PUT", body: JSON.stringify({ playerId: value || null }) }); onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function removeMatch() {
    if (!window.confirm("Slet denne manuelle kamp og dens kampbøder?")) return;
    try { await api(`/squads/${dashboard.squad.id}/matches/${match.id}`, { method: "DELETE" }); onSaved(); }
    catch (reason) { onError(reason); }
  }
  const lineupPlayers = lineup.map((playerId) => dashboard.players.find((player) => player.id === playerId)).filter(Boolean);
  const availablePlayers = dashboard.players.filter((player) => !lineup.includes(player.id));
  return <details><summary><span>{match.homeClub || "Kamp"} {match.homeScore ?? "–"}-{match.awayScore ?? "–"} {match.awayClub || ""}<small>{dateLabel(match.date)}{!match.dbuId ? " · Manuel kamp" : ""}</small></span></summary><div className="match-editor-body"><label className="field"><span>Vasker</span><select value={washer} onChange={(event) => void saveWasher(event.target.value)}><option value="">Ikke valgt</option>{dashboard.players.map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}</select></label><span className="field-title">Spillere i kampen</span><div className="lineup-edit-list">{lineupPlayers.map((player) => player && <div key={player.id}><span>{player.name}</span><button type="button" onClick={() => void saveLineup(lineup.filter((id) => id !== player.id))}>Fjern</button></div>)}</div><div className="add-lineup-player"><select value={addPlayerId} onChange={(event) => setAddPlayerId(event.target.value)}><option value="">Tilføj en anden spiller</option>{availablePlayers.map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}</select><button type="button" disabled={!addPlayerId} onClick={() => { void saveLineup([...lineup, Number(addPlayerId)]); setAddPlayerId(""); }}>Tilføj</button></div>{match.lineupLocked && match.dbuId && <button className="text-danger" type="button" onClick={() => void resetLineup()}>Brug DBU-holdopstilling igen</button>}{!match.dbuId && <button className="danger-button" type="button" onClick={() => void removeMatch()}>Slet manuel kamp</button>}</div></details>;
}

function DbuTool({ dashboard, onError, onSaved }: { dashboard: Dashboard; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [syncing, setSyncing] = useState(false);
  async function add(event: FormEvent) {
    event.preventDefault();
    try { await api(`/squads/${dashboard.squad.id}/seasons/${dashboard.season.id}/dbu-sources`, jsonBody({ label, url })); setLabel(""); setUrl(""); onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function remove(sourceId: number) {
    try { await api(`/squads/${dashboard.squad.id}/seasons/${dashboard.season.id}/dbu-sources/${sourceId}`, { method: "DELETE" }); onSaved(); }
    catch (reason) { onError(reason); }
  }
  async function sync() {
    setSyncing(true);
    try { await api(`/squads/${dashboard.squad.id}/sync`, { method: "POST" }); onSaved(); }
    catch (reason) { onError(reason); }
    finally { setSyncing(false); }
  }
  return <><div className="admin-rows">{dashboard.dbuSources.map((source) => <article key={source.id}><div><b>{source.label}</b><small>{source.url}</small></div><button className="text-danger" onClick={() => void remove(source.id)}>Fjern</button></article>)}</div><form onSubmit={add}><Field label="Navn" hint="Fx Senior 2" value={label} onChange={setLabel} required /><Field label="DBU kampprogram-link" value={url} onChange={setUrl} required /><button className="save-button">Tilføj link</button></form><button className="secondary-save" onClick={() => void sync()} disabled={syncing}>{syncing ? "Opdaterer…" : "Opdater fra DBU nu"}</button></>;
}

function RuleTool({ dashboard, onError, onSaved }: { dashboard: Dashboard; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [name, setName] = useState(""); const [amount, setAmount] = useState(""); const [type, setType] = useState("TEAM_FINE");
  async function submit(event: FormEvent) { event.preventDefault(); try { await api(`/squads/${dashboard.squad.id}/fine-rules`, jsonBody({ name, amount, type, description: "" })); setName(""); setAmount(""); setType("TEAM_FINE"); onSaved(); } catch (reason) { onError(reason); } }
  return <><div className="admin-rows">{dashboard.rules.map((rule) => <article key={rule.id}><div><b>{rule.name}</b><small>{rule.type}</small></div><strong>{money(rule.amount)}</strong></article>)}</div><form onSubmit={submit}><Field label="Navn" value={name} onChange={setName} required /><Field label="Beløb" type="number" value={amount} onChange={setAmount} required /><Select label="Type" value={type} onChange={setType} options={[{ value: "TEAM_FINE", label: "Almindelig bøde" }, { value: "WIN_FINE", label: "Sejr" }, { value: "DRAW_FINE", label: "Uafgjort" }, { value: "LOSE_FINE", label: "Nederlag" }, { value: "SCORED_GOAL", label: "Mål scoret" }, { value: "CONCEDED_GOAL", label: "Mål indkasseret" }]} /><button className="save-button">Tilføj takst</button></form></>;
}

function PermissionTool({ squadId, onError }: { squadId: number; onError: (reason: unknown) => void }) {
  const [users, setUsers] = useState<PermissionUser[]>([]); const [userId, setUserId] = useState(0); const [selected, setSelected] = useState<Permission[]>([]);
  async function load() { try { const result = await api<{ users: PermissionUser[] }>(`/squads/${squadId}/permissions`); setUsers(result.users); const current = result.users.find((item) => item.id === userId) || result.users[0]; if (current) { setUserId(current.id); setSelected(current.isOwner ? permissionKeys : current.permissions); } } catch (reason) { onError(reason); } }
  useEffect(() => { void load(); }, [squadId]);
  function choose(id: number) { const selectedUser = users.find((item) => item.id === id); setUserId(id); setSelected(selectedUser?.isOwner ? permissionKeys : selectedUser?.permissions || []); }
  function toggle(permission: Permission) { setSelected((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission]); }
  async function save() { try { await api(`/squads/${squadId}/permissions/${userId}`, { method: "PUT", body: JSON.stringify({ permissions: selected }) }); await load(); } catch (reason) { onError(reason); } }
  const selectedUser = users.find((item) => item.id === userId);
  return <><Select label="Bruger" value={String(userId)} onChange={(value) => choose(Number(value))} options={users.map((item) => ({ value: item.id, label: `${item.username}${item.isOwner ? " · ejer" : ""}` }))} /><div className="checkbox-grid">{permissionKeys.map((permission) => <label key={permission}><input type="checkbox" disabled={selectedUser?.isOwner} checked={selected.includes(permission)} onChange={() => toggle(permission)} />{permissionLabels[permission]}</label>)}</div><button className="save-button" disabled={selectedUser?.isOwner} onClick={() => void save()}>Gem rettigheder</button></>;
}

function NewSquad({ onError }: { onError: (reason: unknown) => void }) {
  const [name, setName] = useState(""); const [dbuClubName, setDbuClubName] = useState(""); const [links, setLinks] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); try { await api("/squads", jsonBody({ name, dbuClubName, dbuSeasonUrls: links.split("\n") })); window.location.reload(); } catch (reason) { onError(reason); } }
  return <form onSubmit={submit}><Field label="Holdnavn" value={name} onChange={setName} required /><Field label="Klubnavn på DBU" value={dbuClubName} onChange={setDbuClubName} required /><label className="field"><span>DBU-links · ét pr. linje</span><textarea rows={3} value={links} onChange={(event) => setLinks(event.target.value)} /></label><button className="save-button">Opret hold</button></form>;
}

function Field({ label, value, onChange, type = "text", hint, required = false }: { label: string; value: string; onChange: (value: string) => void; type?: string; hint?: string; required?: boolean }) {
  return <label className="field"><span>{label}{hint && <small>{hint}</small>}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} required={required} /></label>;
}

function Select({ label, value, onChange, options, required = false }: { label: string; value: string; onChange: (value: string) => void; options: { value: string | number; label: string }[]; required?: boolean }) {
  return <label className="field"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} required={required}><option value="">Vælg…</option>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>;
}

import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import AdminPanel from "./AdminPanel";
import { api, jsonBody, setCsrfToken } from "./api";
import type { Charge, Dashboard, PaymentSettings, Permission, Player, SetupStatus, Squad, User } from "./types";

type View = "home" | "login" | "register" | "dashboard";

function money(value: number) {
  return `${new Intl.NumberFormat("da-DK", { maximumFractionDigits: 2 }).format(value)} kr.`;
}

function dateLabel(value: string | null) {
  if (!value) return "Dato mangler";
  return new Intl.DateTimeFormat("da-DK", { dateStyle: "medium" }).format(new Date(value));
}

function hasPermission(user: User | null, squadId: number, permission: Permission) {
  return Boolean(user?.isOwner || user?.permissions.some((item) => item.squadId === squadId && item.permission === permission));
}

export default function App() {
  const [view, setView] = useState<View>("home");
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [squad, setSquad] = useState<Squad | null>(null);
  const [error, setError] = useState("");

  async function loadSetup() {
    const result = await api<SetupStatus>("/setup/status");
    setSetup(result);
    setSquad((current) => current || result.squads[0] || null);
    return result;
  }

  useEffect(() => {
    void (async () => {
      try {
        const status = await loadSetup();
        if (status.needsSetup) return;
        const session = await api<{ user: User; csrfToken: string }>("/auth/me");
        setUser(session.user);
        setCsrfToken(session.csrfToken);
        setSquad(
          status.squads.find((item) => item.id === session.user.playerSquadId)
          || status.squads.find((item) => item.id === session.user.permissions[0]?.squadId)
          || status.squads[0]
          || null,
        );
        setView("dashboard");
      } catch {
        // Not being logged in is the normal public state.
      }
    })();
  }, []);

  function fail(reason: unknown) {
    setError(reason instanceof Error ? reason.message : "Der skete en fejl. Prøv igen.");
  }

  async function signedIn(result: { user: User; csrfToken: string }) {
    setUser(result.user);
    setCsrfToken(result.csrfToken);
    setError("");
    const status = await loadSetup();
    setSquad(
      status.squads.find((item) => item.id === result.user.playerSquadId)
      || status.squads[0]
      || null,
    );
    setView("dashboard");
  }

  async function logout() {
    try { await api("/auth/logout", { method: "POST" }); } catch { /* Session is already gone. */ }
    setCsrfToken("");
    setUser(null);
    setView("home");
  }

  if (setup?.needsSetup) {
    return <SetupScreen onDone={signedIn} onError={fail} error={error} />;
  }

  if (view === "login") {
    return <LoginScreen onDone={signedIn} onBack={() => setView("home")} onError={fail} error={error} />;
  }

  if (view === "register") {
    return <RegisterScreen squads={setup?.squads || []} onDone={signedIn} onBack={() => setView("home")} onError={fail} error={error} />;
  }

  if (view === "dashboard" && squad) {
    return (
      <DashboardScreen
        squad={squad}
        squads={setup?.squads || []}
        user={user}
        onSquad={setSquad}
        onLogin={() => setView("login")}
        onLogout={logout}
        onHome={() => setView("home")}
        onError={fail}
        error={error}
      />
    );
  }

  return (
    <HomeScreen
      clubName={setup?.clubName}
      squads={setup?.squads || []}
      onPublic={(selected) => { setSquad(selected); setView("dashboard"); }}
      onLogin={() => setView("login")}
      onRegister={() => setView("register")}
    />
  );
}

function Shell({ children, title = "Bødekassen", onHome }: { children: ReactNode; title?: string; onHome?: () => void }) {
  return (
    <main className="app-shell">
      <header className="app-header">
        <button className="logo" onClick={onHome} type="button"><b>ØB</b><span>{title}</span></button>
      </header>
      {children}
    </main>
  );
}

function HomeScreen({ clubName, squads, onPublic, onLogin, onRegister }: { clubName?: string | null; squads: Squad[]; onPublic: (squad: Squad) => void; onLogin: () => void; onRegister: () => void }) {
  const [showSquads, setShowSquads] = useState(false);
  function continueWithoutLogin() {
    if (squads.length === 1) onPublic(squads[0]);
    else setShowSquads(true);
  }
  return (
    <Shell title={clubName || "Bødekassen"}>
      <section className="welcome">
        <span className="eyebrow">KLUBBENS BØDEKASSE</span>
        <h1>Hvad skylder jeg?</h1>
        <p>Find dit navn, se dine bøder og betal det rigtige beløb.</p>
        <button className="primary-action" onClick={continueWithoutLogin}>Se uden login</button>
        <button className="secondary-action" onClick={onLogin}>Log ind</button>
        <button className="simple-link" onClick={onRegister}>Opret bruger</button>
        {showSquads && <div className="simple-list squad-list"><strong>Vælg hold</strong>{squads.map((item) => <button key={item.id} onClick={() => onPublic(item)}>{item.name}<span>→</span></button>)}</div>}
      </section>
    </Shell>
  );
}

function SetupScreen({ onDone, onError, error }: { onDone: (result: { user: User; csrfToken: string }) => void; onError: (reason: unknown) => void; error: string }) {
  const [form, setForm] = useState({ clubName: "", squadName: "", dbuClubName: "", dbuLinks: "", seasonName: String(new Date().getFullYear()), mobilePayBoxNumber: "", mobilePayUrl: "", username: "", password: "" });
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      const result = await api<{ user: User; csrfToken: string }>("/setup", jsonBody({ ...form, dbuSeasonUrls: form.dbuLinks.split("\n") }));
      setCsrfToken(result.csrfToken); onDone(result);
    } catch (reason) { onError(reason); } finally { setBusy(false); }
  }
  return (
    <Shell>
      <FormCard title="Start bødekassen" intro="Du gør kun dette én gang.">
        <form onSubmit={submit}>
          <Field label="Klub" value={form.clubName} onChange={(value) => setForm({ ...form, clubName: value })} required />
          <Field label="Hold / fælles bødekasse" value={form.squadName} onChange={(value) => setForm({ ...form, squadName: value })} required />
          <Field label="Klubnavn på DBU" hint="Fx Øster Sundby" value={form.dbuClubName} onChange={(value) => setForm({ ...form, dbuClubName: value })} required />
          <TextArea label="DBU-links" hint="Ét kampprogram-link pr. linje" value={form.dbuLinks} onChange={(value) => setForm({ ...form, dbuLinks: value })} />
          <Field label="Sæson" value={form.seasonName} onChange={(value) => setForm({ ...form, seasonName: value })} required />
          <Field label="MobilePay Box-nummer" hint="Fx 1783QN" value={form.mobilePayBoxNumber} onChange={(value) => setForm({ ...form, mobilePayBoxNumber: value })} />
          <Field label="MobilePay delelink" hint="Kopiér linket fra Del i Box" value={form.mobilePayUrl} onChange={(value) => setForm({ ...form, mobilePayUrl: value })} />
          <Field label="Dit brugernavn" value={form.username} onChange={(value) => setForm({ ...form, username: value })} required />
          <Field label="Adgangskode" hint="Valgfri" type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} />
          <button className="primary-action" disabled={busy}>{busy ? "Opretter…" : "Opret"}</button>
          {error && <ErrorMessage text={error} />}
        </form>
      </FormCard>
    </Shell>
  );
}

function LoginScreen({ onDone, onBack, onError, error }: { onDone: (result: { user: User; csrfToken: string }) => void; onBack: () => void; onError: (reason: unknown) => void; error: string }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      await api("/auth/login", jsonBody({ username, password }));
      onDone(await api<{ user: User; csrfToken: string }>("/auth/me"));
    } catch (reason) { onError(reason); } finally { setBusy(false); }
  }
  return <Shell onHome={onBack}><FormCard title="Log ind" intro="Store og små bogstaver er ligegyldige."><form onSubmit={submit}><Field label="Brugernavn" value={username} onChange={setUsername} required /><Field label="Adgangskode" hint="Kan være tom" type="password" value={password} onChange={setPassword} /><button className="primary-action" disabled={busy}>{busy ? "Logger ind…" : "Log ind"}</button><button className="simple-link" type="button" onClick={onBack}>Tilbage</button>{error && <ErrorMessage text={error} />}</form></FormCard></Shell>;
}

function RegisterScreen({ squads, onDone, onBack, onError, error }: { squads: Squad[]; onDone: (result: { user: User; csrfToken: string }) => void; onBack: () => void; onError: (reason: unknown) => void; error: string }) {
  const [squadId, setSquadId] = useState(squads[0]?.id || 0);
  const [players, setPlayers] = useState<{ id: number; name: string }[]>([]);
  const [playerId, setPlayerId] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const selected = squads.find((item) => item.id === squadId);
    if (selected) void api<{ players: { id: number; name: string }[] }>(`/public/squads/${selected.slug}/players`).then((result) => setPlayers(result.players));
  }, [squadId, squads]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      await api("/auth/register", jsonBody({ username, password, playerId: playerId || null }));
      onDone(await api<{ user: User; csrfToken: string }>("/auth/me"));
    } catch (reason) { onError(reason); } finally { setBusy(false); }
  }
  return <Shell onHome={onBack}><FormCard title="Opret bruger" intro="Vælg dit spillernavn. Adgangskode er valgfri."><form onSubmit={submit}><Field label="Brugernavn" value={username} onChange={setUsername} required /><Field label="Adgangskode" hint="Valgfri" type="password" value={password} onChange={setPassword} /><label className="field"><span>Hold</span><select value={squadId} onChange={(event) => setSquadId(Number(event.target.value))}>{squads.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Hvem er du?</span><select value={playerId} onChange={(event) => setPlayerId(event.target.value)}><option value="">Jeg er ikke spiller</option>{players.map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}</select></label><button className="primary-action" disabled={busy}>{busy ? "Opretter…" : "Opret bruger"}</button><button className="simple-link" type="button" onClick={onBack}>Tilbage</button>{error && <ErrorMessage text={error} />}</form></FormCard></Shell>;
}

function DashboardScreen({ squad, squads, user, onSquad, onLogin, onLogout, onHome, onError, error }: { squad: Squad; squads: Squad[]; user: User | null; onSquad: (squad: Squad) => void; onLogin: () => void; onLogout: () => void; onHome: () => void; onError: (reason: unknown) => void; error: string }) {
  const [loadedDashboard, setDashboard] = useState<Dashboard | null>(null);
  const [search, setSearch] = useState("");
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  const [recentPlayerIds, setRecentPlayerIds] = useState<number[]>([]);
  const [playerListOpen, setPlayerListOpen] = useState(true);
  const loadRequest = useRef(0);
  const dashboard = loadedDashboard?.squad.id === squad.id ? loadedDashboard : null;
  async function load(seasonId?: number, background = false) {
    const requestId = ++loadRequest.current;
    if (!background) setLoading(true);
    try {
      const base = user ? `/squads/${squad.id}/dashboard` : `/public/squads/${squad.slug}/dashboard`;
      const result = await api<Dashboard>(`${base}${seasonId ? `?seasonId=${seasonId}` : ""}`);
      if (requestId === loadRequest.current) setDashboard(result);
    } catch (reason) {
      if (requestId === loadRequest.current) onError(reason);
    } finally {
      if (!background && requestId === loadRequest.current) setLoading(false);
    }
  }
  useEffect(() => {
    void load();
    return () => { loadRequest.current += 1; };
  }, [squad.id, user?.id, version]);
  useEffect(() => {
    if (!user || loading) return;
    const interval = window.setInterval(() => void load(dashboard?.season.id, true), 30_000);
    return () => window.clearInterval(interval);
  }, [squad.id, user?.id, dashboard?.season.id, loading]);
  useEffect(() => {
    setSearch("");
    setSelectedPlayerId(null);
    setPlayerListOpen(true);
    if (user) { setRecentPlayerIds([]); return; }
    try {
      const stored = JSON.parse(window.localStorage.getItem(`recent-players:${squad.slug}`) || "[]");
      setRecentPlayerIds(Array.isArray(stored) ? stored.filter((item): item is number => Number.isInteger(item)).slice(0, 10) : []);
    } catch { setRecentPlayerIds([]); }
  }, [squad.slug, user?.id]);
  const ownPlayer = dashboard?.players.find((player) => player.id === user?.playerId && player.squadId === squad.id) || null;
  const selectedPlayer = dashboard?.players.find((player) => player.id === selectedPlayerId) || null;
  const canApproveFines = hasPermission(user, squad.id, "approve_fine_requests");
  const canManageFines = canApproveFines || hasPermission(user, squad.id, "issue_fines");
  const normalizedSearch = search.trim().toLocaleLowerCase("da-DK");
  const debtSortedPlayers = [...(dashboard?.players || [])].sort((left, right) => {
    const debtDifference = Math.max(-right.balance, 0) - Math.max(-left.balance, 0);
    return debtDifference || left.name.localeCompare(right.name, "da-DK");
  });
  const recentPlayers = recentPlayerIds.flatMap((id) => debtSortedPlayers.find((player) => player.id === id) || []);
  const defaultPlayers = !user && recentPlayers.length
    ? [...recentPlayers, ...debtSortedPlayers.filter((player) => !recentPlayerIds.includes(player.id))]
    : debtSortedPlayers;
  const visiblePlayers = (normalizedSearch
    ? debtSortedPlayers.filter((player) => player.name.toLocaleLowerCase("da-DK").includes(normalizedSearch))
    : defaultPlayers
  );
  function openPlayer(player: Player) {
    setSelectedPlayerId(player.id);
    if (user) return;
    const next = [player.id, ...recentPlayerIds.filter((id) => id !== player.id)].slice(0, 10);
    setRecentPlayerIds(next);
    try { window.localStorage.setItem(`recent-players:${squad.slug}`, JSON.stringify(next)); } catch { /* Private browsing can disable storage. */ }
  }

  return (
    <Shell title={squad.name} onHome={onHome}>
      <nav className="dashboard-nav">
        <div className="nav-selects">
          {squads.length > 1 && <select value={squad.id} onChange={(event) => onSquad(squads.find((item) => item.id === Number(event.target.value)) || squad)}>{squads.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}
          {dashboard && dashboard.seasons.length > 1 && <select value={dashboard.season.id} onChange={(event) => void load(Number(event.target.value))}>{dashboard.seasons.map((season) => <option key={season.id} value={season.id}>{season.name}</option>)}</select>}
        </div>
        {user ? <button className="small-button" onClick={onLogout}>Log ud</button> : <button className="small-button" onClick={onLogin}>Log ind</button>}
      </nav>

      {loading && <p className="loading">Henter saldo…</p>}
      {dashboard && <div className="dashboard">
        {user && <button className="primary-action request-button" onClick={() => setRequestOpen(true)}>{canApproveFines ? "Giv bøde" : "Anmod om bøde"}</button>}

        {ownPlayer && <OwnBalance player={ownPlayer} payment={dashboard.payment} onDetails={() => setSelectedPlayerId(ownPlayer.id)} />}

        <section className="search-card">
          <span className="eyebrow">{ownPlayer ? "FIND EN HOLDKAMMERAT" : "FIND DIG SELV"}</span>
          <h1>{ownPlayer ? "Søg på holdet" : "Hvad skylder jeg?"}</h1>
          <label className="search-field"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); if (event.target.value.trim()) setPlayerListOpen(true); }} placeholder="Skriv et navn…" autoComplete="off" /></label>
          <div className="result-heading-row"><span className="result-heading">{normalizedSearch ? "Søgeresultater" : !user && recentPlayers.length ? "Senest set først" : "Skylder mest"}</span><button type="button" aria-expanded={playerListOpen} onClick={() => setPlayerListOpen((open) => !open)}>{playerListOpen ? "Skjul" : `Vis ${visiblePlayers.length}`}</button></div>
          {playerListOpen && <div className="player-results">
            {visiblePlayers.map((player) => <div className="player-result-row" key={player.id}><button className="player-result-main" type="button" onClick={() => openPlayer(player)}><span><b>{player.name}</b><small>{player.fines.length} bøder</small></span><strong className={player.balance < 0 ? "debt" : "settled"}>{player.balance < 0 ? `Skylder ${money(-player.balance)}` : "Betalt"}</strong><i>›</i></button>{!user && recentPlayerIds.includes(player.id) && player.balance < 0 && <PaymentButton player={player} payment={dashboard.payment} compact />}</div>)}
            {visiblePlayers.length === 0 && <p>Ingen spillere matcher søgningen.</p>}
          </div>}
        </section>

        <section className="balance-pair">
          <div><span>I bødekassen nu</span><strong>{money(dashboard.balanceSummary.boxBalance)}</strong></div>
          <div><span>Når alle har betalt</span><strong>{money(dashboard.balanceSummary.ifEveryonePays)}</strong><small>{dashboard.balanceSummary.debtors} mangler at betale</small></div>
        </section>

        <details className="fold">
          <summary>Bødetakster <span>{dashboard.rules.length}</span></summary>
          <div className="fold-content simple-rows">{dashboard.rules.map((rule) => <div key={rule.id}><span><b>{rule.name}</b><small>{rule.description}</small></span><strong>{money(rule.amount)}</strong></div>)}</div>
        </details>

        {dashboard.expenses.length > 0 && <details className="fold"><summary>Penge brugt fra boksen <span>{dashboard.expenses.length}</span></summary><div className="fold-content simple-rows">{dashboard.expenses.map((item) => <div key={item.id}><span><b>{item.name || "Ukendt"}</b><small>{dateLabel(item.date)}{item.message ? ` · ${item.message}` : ""}</small></span><strong>{money(item.amount)}</strong></div>)}</div></details>}

        {user && <AdminPanel key={dashboard.squad.id} dashboard={dashboard} user={user} onFailure={onError} onRefresh={() => setVersion((value) => value + 1)} />}
      </div>}

      {selectedPlayer && dashboard && <PlayerSheet player={selectedPlayer} payment={dashboard.payment} squadId={squad.id} canManageFines={canManageFines} onClose={() => setSelectedPlayerId(null)} onError={onError} onSaved={() => setVersion((value) => value + 1)} />}
      {requestOpen && dashboard && <RequestSheet dashboard={dashboard} instant={canApproveFines} onClose={() => setRequestOpen(false)} onError={onError} onSaved={() => { setRequestOpen(false); setVersion((value) => value + 1); }} />}
      {error && <ErrorMessage text={error} />}
    </Shell>
  );
}

function OwnBalance({ player, payment, onDetails }: { player: Player; payment: PaymentSettings; onDetails: () => void }) {
  const debt = Math.max(-player.balance, 0);
  return <section className={`own-balance ${debt ? "owes" : "clear"}`}><span className="eyebrow">DIN SALDO</span><h1>{debt ? `Du skylder ${money(debt)}` : "Du er helt ajour"}</h1><p>{debt ? `${player.fines.length} bøder. Se præcis hvorfor nedenfor.` : "Der er ikke noget, du skal betale."}</p><div className="action-row"><button className="secondary-action" onClick={onDetails}>Se hvorfor</button>{debt > 0 && <PaymentButton player={player} payment={payment} />}</div></section>;
}

function PlayerSheet({ player, payment, squadId, canManageFines, onClose, onError, onSaved }: { player: Player; payment: PaymentSettings; squadId: number; canManageFines: boolean; onClose: () => void; onError: (reason: unknown) => void; onSaved: () => void }) {
  const debt = Math.max(-player.balance, 0);
  return <div className="sheet-backdrop" onMouseDown={onClose}><section className="bottom-sheet" onMouseDown={(event) => event.stopPropagation()}><button className="sheet-close" onClick={onClose} aria-label="Luk">×</button><span className="eyebrow">SALDO FOR</span><h2>{player.name}</h2><div className={`amount-due ${debt ? "debt" : "settled"}`}><span>{debt ? "Skylder" : "Status"}</span><strong>{debt ? money(debt) : "Betalt"}</strong></div>{debt > 0 && <PaymentButton player={player} payment={payment} full />}<h3>Hvorfor?</h3>{player.fines.length === 0 ? <p className="empty-copy">Ingen bøder.</p> : <div className="fine-list">{player.fines.map((fine) => canManageFines ? <FineEditor key={`${fine.id}-${fine.title}-${fine.description}-${fine.amount}`} fine={fine} playerName={player.name} squadId={squadId} onError={onError} onSaved={onSaved} /> : <article key={fine.id}><div><b>{fine.title}</b><p>{fine.description || "Ingen ekstra beskrivelse"}</p><small>{dateLabel(fine.date)}</small></div><strong>{money(fine.amount)}</strong></article>)}</div>}<details className="payments-fold"><summary>Se betalinger ({player.payments.length})</summary><div className="simple-rows">{player.payments.map((item) => <div key={item.id}><span><b>{item.message || item.name || "MobilePay"}</b><small>{dateLabel(item.date)}</small></span><strong>{money(item.amount)}</strong></div>)}</div></details></section></div>;
}

function FineEditor({ fine, playerName, squadId, onError, onSaved }: { fine: Charge; playerName: string; squadId: number; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [title, setTitle] = useState(fine.title);
  const [description, setDescription] = useState(fine.description);
  const [amount, setAmount] = useState(String(fine.amount));
  const [busy, setBusy] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      await api(`/squads/${squadId}/charges/${fine.id}`, { method: "PATCH", body: JSON.stringify({ title, description, amount }) });
      onSaved();
    } catch (reason) { onError(reason); } finally { setBusy(false); }
  }
  async function remove() {
    if (!window.confirm(`Slet bøden "${fine.title}" fra ${playerName}? Spillerens saldo bliver rettet med det samme.`)) return;
    setBusy(true);
    try {
      await api(`/squads/${squadId}/charges/${fine.id}`, { method: "DELETE" });
      onSaved();
    } catch (reason) { onError(reason); setBusy(false); }
  }
  return <details className="fine-editor"><summary><span><b>{fine.title}</b><small>{dateLabel(fine.date)} · Tryk for at redigere</small></span><strong>{money(fine.amount)}</strong></summary><form onSubmit={save}><Field label="Navn på bøde" value={title} onChange={setTitle} required /><TextArea label="Beskrivelse" value={description} onChange={setDescription} /><Field label="Beløb" type="number" value={amount} onChange={setAmount} required /><button className="secondary-save" disabled={busy}>{busy ? "Gemmer…" : "Gem ændringer"}</button><button className="danger-button" type="button" disabled={busy} onClick={() => void remove()}>Slet bøde</button></form></details>;
}

function PaymentButton({ player, payment, full = false, compact = false }: { player: Player; payment: PaymentSettings; full?: boolean; compact?: boolean }) {
  const debt = Math.max(-player.balance, 0);
  const href = payment.paymentUrl ? mobilePayLink(payment.paymentUrl, debt, player.name) : null;
  async function copy() {
    await navigator.clipboard.writeText(`MobilePay Box ${payment.boxNumber || ""}\nBeløb: ${money(debt)}\nNavn: ${player.name}`);
  }
  if (href) return <a className={`payment-button ${full ? "full" : ""} ${compact ? "compact" : ""}`} href={href}>{compact ? "Betal" : `Åbn MobilePay${payment.boxNumber ? ` Box ${payment.boxNumber}` : ""} · ${money(debt)}`}</a>;
  if (payment.boxNumber) return <button className={`payment-button ${full ? "full" : ""} ${compact ? "compact" : ""}`} type="button" onClick={() => void copy()}>{compact ? "Kopiér betaling" : `Kopiér betaling · Box ${payment.boxNumber}`}</button>;
  return null;
}

function mobilePayLink(base: string, amount: number, playerName: string) {
  try {
    const url = new URL(base);
    url.searchParams.set("amount", String(Math.round(amount * 100)));
    url.searchParams.set("message", `Bødekasse - ${playerName}`);
    return url.toString();
  } catch { return base; }
}

function RequestSheet({ dashboard, instant, onClose, onError, onSaved }: { dashboard: Dashboard; instant: boolean; onClose: () => void; onError: (reason: unknown) => void; onSaved: () => void }) {
  const [ruleId, setRuleId] = useState("");
  const [minutesLate, setMinutesLate] = useState("");
  const [playerIds, setPlayerIds] = useState<number[]>([]);
  const [playerSearch, setPlayerSearch] = useState("");
  const [customTitle, setCustomTitle] = useState("");
  const [customAmount, setCustomAmount] = useState("");
  const [customDescription, setCustomDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const requestRules = dashboard.rules.filter((rule) => rule.type === "TEAM_FINE" || rule.type === "LATE_FINE");
  const normalizedPlayerSearch = playerSearch.trim().toLocaleLowerCase("da-DK");
  const matchingPlayers = normalizedPlayerSearch ? dashboard.players.filter((player) => !playerIds.includes(player.id) && player.name.toLocaleLowerCase("da-DK").includes(normalizedPlayerSearch)).slice(0, 10) : [];
  const selectedPlayers = playerIds.flatMap((id) => dashboard.players.find((player) => player.id === id) || []);
  const isCustom = ruleId === "custom";
  const selectedRule = requestRules.find((rule) => String(rule.id) === ruleId);
  const isLateFine = selectedRule?.type === "LATE_FINE";
  const validMinutesLate = !isLateFine || /^[1-9]\d*$/.test(minutesLate);
  const calculatedAmount = selectedRule ? selectedRule.amount + (isLateFine && validMinutesLate ? Number(minutesLate) * selectedRule.perMinuteAmount : 0) : 0;
  const validCustomFine = !isCustom || (customTitle.trim().length > 0 && Number(customAmount) > 0);
  function togglePlayer(playerId: number) {
    setPlayerIds((current) => current.includes(playerId) ? current.filter((id) => id !== playerId) : [...current, playerId]);
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      const fine = isCustom ? { title: customTitle, amount: customAmount, description: customDescription } : { ruleId, ...(isLateFine ? { minutesLate } : {}) };
      await api(`/squads/${dashboard.squad.id}/fine-requests`, jsonBody({ seasonId: dashboard.season.id, playerIds, ...fine }));
      onSaved();
    } catch (reason) { onError(reason); } finally { setBusy(false); }
  }
  return (
    <div className="sheet-backdrop" onMouseDown={onClose}>
      <form className="bottom-sheet" onMouseDown={(event) => event.stopPropagation()} onSubmit={submit}>
        <button className="sheet-close" type="button" onClick={onClose}>×</button>
        <span className="eyebrow">{instant ? "GIV BØDE" : "ANMOD OM BØDE"}</span>
        <h2>Vælg bøde og spillere</h2>
        <label className="field"><span>Bøde</span><select value={ruleId} onChange={(event) => { setRuleId(event.target.value); setMinutesLate(""); }} required><option value="">Vælg bøde</option>{requestRules.map((rule) => <option key={rule.id} value={rule.id}>{rule.name} · {rule.type === "LATE_FINE" ? `${money(rule.amount)} + ${money(rule.perMinuteAmount)}/min.` : money(rule.amount)}</option>)}<option value="custom">Anden bøde…</option></select></label>
        {isCustom && <div className="custom-fine-fields"><Field label="Navn på bøde" value={customTitle} onChange={setCustomTitle} required /><Field label="Beløb" type="number" value={customAmount} onChange={setCustomAmount} required /><TextArea label="Beskrivelse" value={customDescription} onChange={setCustomDescription} /></div>}
        {isLateFine && selectedRule && <div className="late-fine-fields"><Field label="Minutter for sent" type="number" value={minutesLate} onChange={setMinutesLate} min="1" step="1" required /><div className="late-fine-total"><span>Beregnet bøde</span><strong>{validMinutesLate ? money(calculatedAmount) : "Angiv minutter"}</strong><small>{money(selectedRule.amount)} fast + {validMinutesLate ? minutesLate : "0"} × {money(selectedRule.perMinuteAmount)}</small></div></div>}
        <Field label="Søg efter spiller" hint="Viser højst 10" value={playerSearch} onChange={setPlayerSearch} />
        <div className="fine-player-results">
          {matchingPlayers.map((player) => <button key={player.id} type="button" onClick={() => { togglePlayer(player.id); setPlayerSearch(""); }}>{player.name}<span>+</span></button>)}
          {normalizedPlayerSearch && matchingPlayers.length === 0 && <p className="empty-copy">Ingen spillere matcher.</p>}
        </div>
        <details className="fine-player-dropdown">
          <summary>Vælg fra alle spillere <span>{playerIds.length} valgt</span></summary>
          <div>{dashboard.players.map((player) => <label key={player.id}><input type="checkbox" checked={playerIds.includes(player.id)} onChange={() => togglePlayer(player.id)} />{player.name}</label>)}</div>
        </details>
        {selectedPlayers.length > 0 ? <div className="selected-players"><b>Valgte spillere</b>{selectedPlayers.map((player) => <button key={player.id} type="button" onClick={() => togglePlayer(player.id)}>{player.name}<span>Fjern</span></button>)}</div> : <p className="empty-copy fine-player-help">Søg eller åbn listen for at vælge spillere.</p>}
        <button className="primary-action" disabled={busy || !ruleId || !playerIds.length || !validCustomFine || !validMinutesLate}>{busy ? "Gemmer…" : instant ? "Giv bøde nu" : "Send til godkendelse"}</button>
      </form>
    </div>
  );
}

function FormCard({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return <section className="form-card"><h1>{title}</h1><p>{intro}</p>{children}</section>;
}

function Field({ label, value, onChange, type = "text", hint, required = false, min, step }: { label: string; value: string; onChange: (value: string) => void; type?: string; hint?: string; required?: boolean; min?: string; step?: string }) {
  return <label className="field"><span>{label}{hint && <small>{hint}</small>}</span><input type={type} value={value} min={min} step={step} onChange={(event) => onChange(event.target.value)} required={required} /></label>;
}

function TextArea({ label, value, onChange, hint }: { label: string; value: string; onChange: (value: string) => void; hint?: string }) {
  return <label className="field"><span>{label}{hint && <small>{hint}</small>}</span><textarea rows={3} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function ErrorMessage({ text }: { text: string }) {
  return <p className="error-message">{text}</p>;
}

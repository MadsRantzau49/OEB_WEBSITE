import { useEffect, useState } from "react";
import { api, jsonBody } from "./api";
import type { Charge, Dashboard, Rule } from "./types";

type HoldsportParticipant = {
  holdsportUserId: string;
  name: string;
  playerId: number | null;
  playerName: string | null;
  isCoach: boolean;
  fined: boolean;
  fine: Charge | null;
};

type HoldsportActivity = {
  id: number;
  holdsportId: string;
  title: string;
  type: "Træning" | "Kamp";
  date: string;
  startsAt: string;
  dueAt: string | null;
  captured: boolean;
  url: string;
  lastSyncedAt: string;
  participants: HoldsportParticipant[];
};

type HoldsportOverview = {
  configured: boolean;
  teamId: string | null;
  fineRules: { training: Rule | null; match: Rule | null };
  lastCheckedAt: string | null;
  lastSuccessAt: string | null;
  lastError: string | null;
  activities: HoldsportActivity[];
};

function dateTimeLabel(value: string | null) {
  if (!value) return "Ikke planlagt";
  return new Intl.DateTimeFormat("da-DK", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function leadLabel(rule: Rule | null) {
  if (!rule) return "Mangler";
  const parts = [
    rule.leadDays ? `${rule.leadDays} dage` : "",
    rule.leadHours ? `${rule.leadHours} timer` : "",
    rule.leadMinutes ? `${rule.leadMinutes} minutter` : "",
  ].filter(Boolean);
  return `${parts.join(", ") || "ved start"} før · ${rule.amount} kr.`;
}

function money(value: number) {
  return new Intl.NumberFormat("da-DK", { style: "currency", currency: "DKK" }).format(value);
}

type EventAction = "fine" | "remove" | "retrigger";

export default function HoldsportAdmin({ dashboard, onError, onChanged }: { dashboard: Dashboard; onError: (reason: unknown) => void; onChanged: () => void }) {
  const [overview, setOverview] = useState<HoldsportOverview | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [eventAction, setEventAction] = useState<{ activityId: number; action: EventAction } | null>(null);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [assigningParticipant, setAssigningParticipant] = useState<string | null>(null);
  const [type, setType] = useState<"Alle" | "Træning" | "Kamp">("Alle");
  const [onlyUnmatched, setOnlyUnmatched] = useState(false);
  const squadId = dashboard.squad.id;

  async function load() {
    try {
      setOverview(await api<HoldsportOverview>(`/squads/${squadId}/holdsport`));
    } catch (reason) {
      onError(reason);
    }
  }

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(interval);
  }, [squadId]);

  async function sync() {
    setSyncing(true);
    try {
      const response = await api<{ holdsport: HoldsportOverview }>(`/squads/${squadId}/holdsport/sync`, jsonBody({}));
      setOverview(response.holdsport);
    } catch (reason) {
      onError(reason);
    } finally {
      setSyncing(false);
    }
  }

  async function fineNow(activity: HoldsportActivity) {
    if (!window.confirm("Hent den aktuelle “Ej tilkendegivet”-liste og giv alle matchede spillere bøden nu?")) return;
    setEventAction({ activityId: activity.id, action: "fine" });
    try {
      const response = await api<{ holdsport: HoldsportOverview }>(
        `/squads/${squadId}/holdsport/activities/${activity.id}/fine-now`,
        jsonBody({}),
      );
      setOverview(response.holdsport);
      onChanged();
    } catch (reason) {
      onError(reason);
    } finally {
      setEventAction(null);
    }
  }

  async function removeFines(activity: HoldsportActivity) {
    if (!window.confirm("Fjern alle bøder, som denne aktivitet har oprettet? De bliver ikke oprettet igen automatisk, men du kan genkøre aktiviteten bagefter.")) return;
    setEventAction({ activityId: activity.id, action: "remove" });
    try {
      const response = await api<{ holdsport: HoldsportOverview }>(
        `/squads/${squadId}/holdsport/activities/${activity.id}/fines`,
        { method: "DELETE" },
      );
      setOverview(response.holdsport);
      onChanged();
    } catch (reason) {
      onError(reason);
    } finally {
      setEventAction(null);
    }
  }

  async function retrigger(activity: HoldsportActivity) {
    if (!window.confirm("Hent den aktuelle “Ej tilkendegivet”-liste, fjern aktivitetens gamle bøder og opret nye bøder ud fra listen nu?")) return;
    setEventAction({ activityId: activity.id, action: "retrigger" });
    try {
      const response = await api<{ holdsport: HoldsportOverview }>(
        `/squads/${squadId}/holdsport/activities/${activity.id}/retrigger`,
        jsonBody({}),
      );
      setOverview(response.holdsport);
      onChanged();
    } catch (reason) {
      onError(reason);
    } finally {
      setEventAction(null);
    }
  }

  async function assignPlayer(activity: HoldsportActivity, participant: HoldsportParticipant) {
    const assignmentKey = `${activity.id}:${participant.holdsportUserId}`;
    const playerId = Number(assignments[assignmentKey]);
    if (!playerId) return;
    setAssigningParticipant(assignmentKey);
    try {
      const response = await api<{ holdsport: HoldsportOverview }>(
        `/squads/${squadId}/holdsport/activities/${activity.id}/participants/${encodeURIComponent(participant.holdsportUserId)}/player`,
        { method: "PUT", body: JSON.stringify({ playerId }) },
      );
      setOverview(response.holdsport);
      setAssignments((current) => {
        const next = { ...current };
        delete next[assignmentKey];
        return next;
      });
      onChanged();
    } catch (reason) {
      onError(reason);
    } finally {
      setAssigningParticipant(null);
    }
  }

  if (!overview) return <p className="empty-copy">Henter Holdsport-overblik...</p>;
  const missingRules = !overview.fineRules.training || !overview.fineRules.match;
  const activities = overview.activities.filter((activity) => {
    if (type !== "Alle" && activity.type !== type) return false;
    return !onlyUnmatched || activity.participants.some((participant) => !participant.isCoach && !participant.playerId);
  });
  const noRsvp = overview.activities.reduce((total, activity) => total + activity.participants.filter((item) => !item.isCoach).length, 0);
  const unmatched = overview.activities.reduce((total, activity) => total + activity.participants.filter((item) => !item.isCoach && !item.playerId).length, 0);
  const mutationBusy = syncing || eventAction !== null || assigningParticipant !== null;

  return <div className="holdsport-admin">
    <section className={`holdsport-status ${overview.lastError || !overview.configured || missingRules ? "has-error" : ""}`}>
      <div className="drive-heading"><b>Automatisk Holdsport-kontrol</b><span>{overview.configured ? "Kører automatisk" : "Ikke konfigureret"}</span></div>
      <div className="holdsport-explanation">
        <b>Sådan virker det</b>
        <p>Serveren kontrollerer Holdsport automatisk hvert minut. Når en aktivitets valgte frist nås, hentes den aktuelle liste “Ej tilkendegivet”, og den relevante trænings- eller kampbøde gives til alle matchede spillere. Stab springes altid over.</p>
        <p>Identiske DBU- og Holdsport-navne kobles automatisk. Umatchede navne kan tildeles direkte nedenfor. En behandlet aktivitet kan genkøres, hvis svarfristen ændres. “Opdatér overblik nu” opdaterer kun visningen; automatikken kræver ikke et klik.</p>
      </div>
      {!overview.fineRules.training && <p className="holdsport-warning">Opret en aktiv Holdsport-træningsbøde under “Bødetakster”.</p>}
      {!overview.fineRules.match && <p className="holdsport-warning">Opret en aktiv Holdsport-kampbøde under “Bødetakster”.</p>}
      {overview.lastError && <p className="holdsport-warning">{overview.lastError}</p>}
      <div className="holdsport-rules">
        <span>Træning<strong>{leadLabel(overview.fineRules.training)}</strong></span>
        <span>Kamp<strong>{leadLabel(overview.fineRules.match)}</strong></span>
      </div>
      <div className="holdsport-stats">
        <span>Senest hentet<strong>{dateTimeLabel(overview.lastSuccessAt)}</strong></span>
        <span>Ej tilkendegivet<strong>{noRsvp}</strong></span>
        <span>Mangler Holdsport-navn<strong>{unmatched}</strong></span>
        <span>Aktiviteter<strong>{overview.activities.length}</strong></span>
      </div>
      <button className="save-button" type="button" disabled={mutationBusy || !overview.configured} onClick={() => void sync()}>{syncing ? "Henter fra Holdsport..." : "Opdatér overblik nu"}</button>
    </section>

    <div className="transaction-filter">
      {(["Alle", "Træning", "Kamp"] as const).map((item) => <button key={item} type="button" aria-pressed={type === item} onClick={() => setType(item)}>{item}</button>)}
      <button type="button" aria-pressed={onlyUnmatched} onClick={() => setOnlyUnmatched((value) => !value)}>Mangler Holdsport-navn <span>{unmatched}</span></button>
    </div>

    {activities.length === 0 ? <p className="empty-copy">Ingen aktiviteter matcher filteret.</p> : <div className="holdsport-activities">
      {activities.map((activity) => {
        const isBusy = eventAction?.activityId === activity.id;
        const hasRule = activity.type === "Træning" ? overview.fineRules.training : overview.fineRules.match;
        return <details key={activity.id}>
          <summary>
            <span><b>{activity.title}</b><small>{activity.type} · start {dateTimeLabel(activity.startsAt)} · automatisk kontrol {dateTimeLabel(activity.dueAt)}</small></span>
            <strong>{activity.participants.filter((item) => !item.isCoach).length}</strong>
          </summary>
          <div className="holdsport-activity-body">
            <div className="holdsport-event-actions">
              <a href={activity.url} target="_blank" rel="noreferrer">Åbn på Holdsport</a>
              <div>
                {!activity.captured ? <button className="fine-now" type="button" disabled={mutationBusy || !hasRule} onClick={() => void fineNow(activity)}>{isBusy ? "Giver bøder..." : "Giv bøder nu"}</button> : <>
                  <button className="remove-fines" type="button" disabled={mutationBusy} onClick={() => void removeFines(activity)}>{eventAction?.action === "remove" && isBusy ? "Fjerner..." : "Fjern aktivitetsbøder"}</button>
                  <button className="retrigger-fines" type="button" disabled={mutationBusy || !hasRule} onClick={() => void retrigger(activity)}>{eventAction?.action === "retrigger" && isBusy ? "Genkører..." : "Hent svar og giv bøder igen"}</button>
                </>}
              </div>
            </div>
            <p className="help-text">Genkørsel henter den aktuelle liste, fjerner aktivitetens tidligere bøder og opretter nye med {activity.type === "Træning" ? "træningsbøden" : "kampbøden"}. Umatchede navne får først en bøde, når de tildeles en spiller.</p>
            {activity.participants.length === 0 ? <p className="empty-copy holdsport-empty">Ingen står som “Ej tilkendegivet”.</p> : <div className="holdsport-participants">
              {activity.participants.map((participant) => {
                const assignmentKey = `${activity.id}:${participant.holdsportUserId}`;
                return <div className="holdsport-participant" key={participant.holdsportUserId}>
                  <span>
                    <b>{participant.name}</b>
                    <small>{participant.isCoach ? "Stab, ingen bøde" : participant.playerName ? `Matchet med ${participant.playerName}` : "Mangler spiller"}</small>
                    {!participant.isCoach && (participant.fine
                      ? <small className="holdsport-fine">Bøde: {participant.fine.title} · {money(participant.fine.amount)} · givet til {participant.fine.playerName}</small>
                      : <small>Ingen bøde oprettet</small>)}
                  </span>
                  {!participant.isCoach && !participant.playerId && <div className="assign-row">
                    <select aria-label={`Tildel ${participant.name} til en spiller`} value={assignments[assignmentKey] || ""} onChange={(event) => setAssignments((current) => ({ ...current, [assignmentKey]: event.target.value }))}>
                      <option value="">Vælg spiller</option>
                      {dashboard.players.filter((player) => player.active).map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}
                    </select>
                    <button type="button" disabled={!assignments[assignmentKey] || mutationBusy} onClick={() => void assignPlayer(activity, participant)}>{assigningParticipant === assignmentKey ? "Tildeler..." : "Tildel spiller"}</button>
                  </div>}
                </div>;
              })}
            </div>}
          </div>
        </details>;
      })}
    </div>}
  </div>;
}

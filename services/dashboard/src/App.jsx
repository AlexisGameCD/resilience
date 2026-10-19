import React, { useEffect, useState, useCallback } from "react";

const DET = "/api/detection";
const REM = "/api/remediation";
const ASSIST = "/api/assistant";

function usePoll(fn, ms) {
  useEffect(() => {
    fn();
    const id = setInterval(fn, ms);
    return () => clearInterval(id);
  }, [fn, ms]);
}

function Badge({ status }) {
  const map = {
    nominal: "bg-emerald-100 text-emerald-700",
    resolved: "bg-emerald-100 text-emerald-700",
    acting: "bg-amber-100 text-amber-700",
    verifying: "bg-amber-100 text-amber-700",
    failed: "bg-red-100 text-red-700",
    anomaly: "bg-red-100 text-red-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${map[status] || "bg-iris/30 text-ink"}`}>
      {status}
    </span>
  );
}

function Card({ title, children }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm p-5">
      <h3 className="text-xs uppercase tracking-wider text-iris font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
}

export default function App() {
  const [det, setDet] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [question, setQuestion] = useState("Que faire si payment-api est injoignable ?");
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

  const loadDet = useCallback(async () => {
    try { setDet(await (await fetch(`${DET}/state`)).json()); } catch { /* ignore */ }
  }, []);
  const loadInc = useCallback(async () => {
    try { setIncidents((await (await fetch(`${REM}/incidents`)).json()).incidents || []); } catch { /* ignore */ }
  }, []);

  usePoll(loadDet, 3000);
  usePoll(loadInc, 3000);

  const last = det?.last;
  const serviceState = !last ? "..." : last.anomaly ? "anomaly" : "nominal";
  const current = incidents[0];

  const ask = async () => {
    setAsking(true); setAnswer(null);
    try {
      const r = await fetch(`${ASSIST}/ask`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      setAnswer(await r.json());
    } catch { setAnswer({ answer: "Assistant indisponible.", sources: [] }); }
    finally { setAsking(false); }
  };

  const history = det?.history || [];
  const maxBar = 1.2;

  return (
    <div className="min-h-screen font-sans">
      <header className="bg-ink text-white px-8 py-5">
        <div className="text-[11px] tracking-[0.2em] text-iris">PROJECT RESILIENCE-ALPHA</div>
        <h1 className="text-2xl font-bold">PayAlpha : supervision de la cyber-resilience</h1>
      </header>

      <main className="p-6 max-w-6xl mx-auto grid gap-5">
        {/* Ligne d'etat */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          <Card title="Etat du service">
            <div className="flex items-center gap-2">
              <Badge status={serviceState} />
              <span className="text-sm text-gray-500">payment-api</span>
            </div>
          </Card>
          <Card title="Score d'anomalie (ML)">
            <div className="text-2xl font-bold">{last ? last.score.toFixed(3) : "..."}</div>
            <div className="text-xs text-gray-500">seuil {det ? det.threshold.toFixed(3) : "..."}</div>
          </Card>
          <Card title="Incident en cours">
            {current ? <Badge status={current.status} /> : <span className="text-sm text-gray-500">aucun</span>}
          </Card>
          <Card title="Dernier temps de reprise">
            <div className="text-2xl font-bold">
              {current?.rto_seconds != null ? `${current.rto_seconds}s` : "-"}
            </div>
            <div className="text-xs text-gray-500">RTO observe</div>
          </Card>
        </div>

        {/* Courbe avant / pendant / apres */}
        <Card title="Score d'anomalie : avant, pendant et apres l'incident">
          <div className="flex items-end gap-0.5 h-28">
            {history.map((h, i) => {
              const norm = Math.max(0, Math.min(1, (h.score + maxBar) / maxBar));
              return (
                <div
                  key={i}
                  title={`score ${h.score}`}
                  className={`flex-1 rounded-t ${h.anomaly ? "bg-red-400" : "bg-emerald-400"}`}
                  style={{ height: `${Math.max(4, norm * 100)}%` }}
                />
              );
            })}
            {history.length === 0 && <div className="text-sm text-gray-400">en attente de donnees...</div>}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            Vert : comportement normal. Rouge : ecart detecte par le modele. Le modele distingue sans seuil fixe.
          </div>
        </Card>

        {/* Chronologie des incidents */}
        <Card title="Chronologie des incidents (detecte, remedie, verifie)">
          {incidents.length === 0 && <div className="text-sm text-gray-400">aucun incident enregistre</div>}
          <div className="space-y-4">
            {incidents.slice(0, 4).map((inc) => (
              <div key={inc.id} className="border-l-2 border-iris pl-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold">#{inc.id}</span>
                  <Badge status={inc.status} />
                  <span className="text-sm text-gray-500">{inc.signature}</span>
                  {inc.rto_seconds != null && (
                    <span className="text-xs text-gray-400 ml-auto">RTO {inc.rto_seconds}s</span>
                  )}
                </div>
                <div className="text-xs text-gray-500 mb-1">Decision : {inc.decision}</div>
                <ol className="text-sm space-y-1">
                  {(inc.steps || []).map((s, i) => (
                    <li key={i} className="flex gap-2">
                      <span className={s.ok ? "text-emerald-600" : "text-red-600"}>{s.ok ? "OK" : "KO"}</span>
                      <span className="text-gray-700">{s.type} : {s.detail}</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </Card>

        {/* Assistant RAG */}
        <Card title="Assistant operateur (RAG local)">
          <div className="flex gap-2">
            <input
              className="flex-1 border border-iris rounded-lg px-3 py-2 text-sm"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button
              onClick={ask}
              disabled={asking}
              className="bg-ink text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50"
            >
              {asking ? "..." : "Demander"}
            </button>
          </div>
          {answer && (
            <div className="mt-3 text-sm">
              <p className="whitespace-pre-wrap">{answer.answer}</p>
              {answer.sources?.length > 0 && (
                <div className="text-xs text-gray-500 mt-2">
                  Sources : {answer.sources.join(", ")}
                </div>
              )}
            </div>
          )}
          <div className="text-xs text-gray-400 mt-2">
            Assistant en lecture seule, sans acces privilegie au systeme. Modele local (Ollama, &lt;= 8B).
          </div>
        </Card>
      </main>
    </div>
  );
}

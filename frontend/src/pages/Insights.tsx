import { FormEvent, useState } from "react";
import { Send, Mail, MessageSquare } from "lucide-react";
import { Card, PageHead, State } from "@/components/ui";
import { RecCard } from "@/components/RecCard";
import { AnomalyList } from "@/components/Anomalies";
import { api, useAct, useQ } from "@/lib/api";
import { useApp } from "@/store/app";

const EXAMPLES = ["Why did energy cost rise this week?", "Is there a water leak anywhere?", "Which bins need pickup now?", "How is air quality and what should we tell students?"];

export default function Insights() {
  const user = useApp((s) => s.user)!;
  const [polish, setPolish] = useState(false);
  const recs = useQ<any>("/recommendations", { polish });
  const [q, setQ] = useState("");
  const [log, setLog] = useState<{ q: string; a: any }[]>([]);
  const ask = useAct((question: string) => api("/insights/chat", { method: "POST", body: { question } }));
  const adv = useAct((b: { kind: string; channel: string }) => api("/advisories/generate", { method: "POST", body: b }));
  const [filter, setFilter] = useState("All");
  async function submit(e: FormEvent, text = q) { e.preventDefault(); if (text.trim().length < 3) return; const a = await ask.mutateAsync(text); setLog([{ q: text, a }, ...log]); setQ(""); }
  const list = (recs.data?.recommendations ?? []).filter((r: any) => filter === "All" || r.urgency === filter);
  return (
    <>
      <PageHead title="Insights and actions" subtitle="Recommended actions with owners, impact and the data behind each one. Update the status as work progresses." />
      <div className="grid gap-4 xl:grid-cols-5">
        <div className="space-y-3 xl:col-span-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {["All", "Critical", "High", "Medium", "Low"].map((f) => <button key={f} className={`btn ${filter === f ? "btn-primary" : ""}`} onClick={() => setFilter(f)}>{f}</button>)}
            {recs.data?.llm_enabled && <label className="ml-auto flex items-center gap-1.5 text-xs"><input type="checkbox" checked={polish} onChange={(e) => setPolish(e.target.checked)} />Rewrite top actions with AI (numbers unchanged)</label>}
          </div>
          <State q={recs}>{list.length ? list.map((r: any) => <RecCard key={r.key} rec={r} />) : <p className="text-muted">No actions at this urgency. Nothing needs attention right now.</p>}</State>
        </div>
        <div className="space-y-4 xl:col-span-2">
          <Card title="Ask the dashboard" caption="Answers use only the numbers computed for this facility.">
            <div className="mb-2 flex flex-wrap gap-1.5">{EXAMPLES.map((x) => <button key={x} className="rounded-full border border-line px-2.5 py-1 text-xs hover:bg-raised" onClick={(e) => submit(e as any, x)}>{x}</button>)}</div>
            <form onSubmit={submit} className="flex gap-2"><input className="input flex-1" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about energy, water, air, waste..." aria-label="Your question" /><button className="btn btn-primary" disabled={ask.isPending}><Send size={14} />Ask</button></form>
            {ask.error && <p role="alert" className="mt-2 text-sm text-bad">{ask.error.message}</p>}
            <div className="mt-3 space-y-3">{log.map((m, i) => <div key={i} className="rounded-md border border-line p-3 text-sm"><p className="font-medium">{m.q}</p><p className="mt-1">{m.a.answer}</p><p className="mt-1 text-xs text-muted">{m.a.mode === "llm" ? "Written by AI from the computed facts." : "Template answer from computed facts."} {m.a.disclaimer}</p></div>)}</div>
          </Card>
          {user.role !== "sustainability" && <Card title="Draft an advisory" caption="Creates a ready-to-send notice from current numbers. Review before sending.">
            <div className="flex flex-wrap gap-2">{["air", "heat", "water", "waste"].map((k) => <div key={k} className="flex"><button className="btn rounded-r-none capitalize" onClick={() => adv.mutate({ kind: k, channel: "email" })}><Mail size={13} />{k}</button><button className="btn rounded-l-none border-l-0" aria-label={`${k} SMS`} onClick={() => adv.mutate({ kind: k, channel: "sms" })}><MessageSquare size={13} /></button></div>)}</div>
            {adv.data && <div className="mt-3 rounded-md border border-line p-3 text-sm"><p className="mb-1 text-xs text-muted">{(adv.data as any).channel === "sms" ? `SMS, ${(adv.data as any).chars} characters` : "Email"}</p>{(adv.data as any).subject && <p className="font-medium">{(adv.data as any).subject}</p>}<p className="whitespace-pre-wrap">{(adv.data as any).body}</p>
              <button className="btn mt-2" onClick={() => navigator.clipboard.writeText((adv.data as any).body)}>Copy text</button></div>}
          </Card>}
          <AnomalyList days={7} title="Recent alerts" limit={4} />
        </div>
      </div>
    </>
  );
}

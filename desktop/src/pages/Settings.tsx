// Settings: crash/bug/feedback reporting (Discord webhook + website API),
// feedback form, data locations, about.
import { useEffect, useState } from "react";
import {
  Bug,
  CheckCircle2,
  Flame,
  FolderOpen,
  MessageSquareHeart,
  Send,
  Webhook,
  XCircle,
} from "lucide-react";
import {
  api,
  type AppSettings,
  type DeliveryResult,
  type Live,
  type Meta,
} from "../api";
import { Button, Card, SectionTitle, Segmented, TextInput, Toggle } from "../components/ui";

function DeliveryBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`flex items-center gap-1 text-[11.5px] ${ok ? "text-ok" : "text-mute"}`}>
      {ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
      {label}
    </span>
  );
}

export default function Settings({ live, meta }: { live: Live | null; meta: Meta | null }) {
  const [s, setS] = useState<AppSettings | null>(null);
  const [webhook, setWebhook] = useState("");
  const [siteUrl, setSiteUrl] = useState("");
  const [dirty, setDirty] = useState(false);
  const [testResult, setTestResult] = useState<DeliveryResult | null>(null);
  const [testBusy, setTestBusy] = useState(false);

  const [fbKind, setFbKind] = useState("feedback");
  const [fbMsg, setFbMsg] = useState("");
  const [fbContact, setFbContact] = useState("");
  const [fbState, setFbState] = useState<"idle" | "sending" | "done" | "failed">("idle");

  useEffect(() => {
    api<AppSettings>("/settings").then((cfg) => {
      setS(cfg);
      setWebhook(cfg.report_discord_webhook || "");
      setSiteUrl(cfg.report_site_url || "");
    }).catch(() => {});
  }, []);

  const setFlag = async (key: string, v: boolean) => {
    setS((cur) => (cur ? { ...cur, [key]: v } : cur));
    await api("/settings", { key, value: v });
  };

  const saveEndpoints = async () => {
    await api("/settings", { key: "report_discord_webhook", value: webhook.trim() });
    await api("/settings", { key: "report_site_url", value: siteUrl.trim() });
    setDirty(false);
  };

  const sendTest = async () => {
    setTestBusy(true);
    try {
      setTestResult(await api<DeliveryResult>("/report/test", {}));
    } finally {
      setTestBusy(false);
    }
  };

  const sendFeedback = async () => {
    if (!fbMsg.trim()) return;
    setFbState("sending");
    try {
      await api("/report/feedback", { kind: fbKind, message: fbMsg, contact: fbContact });
      setFbState("done");
      setFbMsg("");
      setTimeout(() => setFbState("idle"), 4000);
    } catch {
      setFbState("failed");
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-5">
        <Card>
          <SectionTitle>Crash & bug reporting</SectionTitle>
          <div className="space-y-4">
            {[
              ["report_enabled", "Save diagnostic reports locally",
               "Crashes write a JSON report (system summary, stack trace, recent log tail) to the crashes folder."],
              ["report_auto_send", "Auto-send crash reports",
               "Deliver reports to the channels below without asking. Off = reports only leave this PC when you click send."],
              ["report_include_logs", "Attach recent log lines",
               "Include the last ~40 log entries so reports are actually debuggable."],
            ].map(([key, label, desc]) => (
              <div key={key} className="flex gap-3.5 items-start">
                <Toggle on={!!s?.[key]} onChange={(v) => setFlag(key, v)} />
                <div>
                  <div className="text-[13.5px] font-semibold">{label}</div>
                  <div className="text-[12px] text-mute leading-relaxed">{desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 space-y-3">
            <div>
              <div className="flex items-center gap-1.5 text-[12px] text-mute mb-1.5">
                <Webhook size={13} /> Discord webhook URL
              </div>
              <TextInput
                value={webhook}
                onChange={(v) => { setWebhook(v); setDirty(true); }}
                placeholder="https://discord.com/api/webhooks/..."
              />
            </div>
            <div>
              <div className="text-[12px] text-mute mb-1.5">Website API endpoint (optional)</div>
              <TextInput
                value={siteUrl}
                onChange={(v) => { setSiteUrl(v); setDirty(true); }}
                placeholder="https://your-site.com/api/reports"
              />
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={saveEndpoints} disabled={!dirty}>Save endpoints</Button>
              <Button kind="ghost" onClick={sendTest} disabled={testBusy}>
                <span className="flex items-center gap-2">
                  <Send size={13} /> {testBusy ? "Sending..." : "Send test report"}
                </span>
              </Button>
              {testResult && (
                <div className="flex items-center gap-3">
                  <DeliveryBadge ok={!!testResult.saved} label="local" />
                  <DeliveryBadge ok={testResult.discord} label="Discord" />
                  <DeliveryBadge ok={testResult.site} label="website" />
                </div>
              )}
            </div>
            <div className="text-[11.5px] text-mute leading-relaxed">
              Create a webhook in your Discord server: Server Settings →
              Integrations → Webhooks → New Webhook, pick your reports
              channel, copy the URL and paste it above. Full walkthrough in
              docs/DISCORD_INTEGRATION.md.
            </div>
          </div>
        </Card>

        <div className="space-y-5">
          <Card delay={0.05}>
            <SectionTitle>Send feedback / report a bug</SectionTitle>
            <div className="space-y-3">
              <Segmented
                id="fb-kind"
                options={["feedback", "bug"]}
                value={fbKind}
                onChange={setFbKind}
              />
              <textarea
                value={fbMsg}
                onChange={(e) => setFbMsg(e.target.value)}
                placeholder={fbKind === "bug"
                  ? "What happened? What did you expect instead?"
                  : "What should Nitro Forge do better?"}
                className="w-full h-28 rounded-xl bg-card2 p-3 text-[12.5px] text-ink outline-none focus:ring-1 focus:ring-accent resize-none placeholder:text-mute"
              />
              <TextInput
                value={fbContact}
                onChange={setFbContact}
                placeholder="Contact (optional - Discord tag or email)"
              />
              <div className="flex items-center gap-3">
                <Button onClick={sendFeedback} disabled={fbState === "sending" || !fbMsg.trim()}>
                  <span className="flex items-center gap-2">
                    {fbKind === "bug" ? <Bug size={14} /> : <MessageSquareHeart size={14} />}
                    {fbState === "sending" ? "Sending..." : fbState === "done" ? "Sent - thank you!" : "Send"}
                  </span>
                </Button>
                {fbState === "failed" && (
                  <span className="text-[12px] text-warn">
                    Could not deliver - is a webhook or site endpoint configured?
                  </span>
                )}
              </div>
            </div>
          </Card>

          <Card delay={0.1}>
            <SectionTitle>About</SectionTitle>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-accent-deep flex items-center justify-center">
                <Flame size={20} className="text-on-accent" />
              </div>
              <div>
                <div className="text-[15px] font-bold">
                  Nitro <span className="text-accent">Forge</span>
                </div>
                <div className="text-[12px] text-mute">
                  v{meta?.version ?? "?"} - game catalog: {meta?.catalog_size.toLocaleString() ?? "?"} titles
                </div>
              </div>
            </div>
            <div className="space-y-1.5 text-[12.5px] text-ink2">
              <div className="flex items-center gap-2">
                <FolderOpen size={13} className="text-mute" />
                <span className="text-mute">Data:</span>
                <span className="truncate" title={meta?.data_dir}>{meta?.data_dir ?? "..."}</span>
              </div>
              <div>
                <span className="text-mute">Privileges: </span>
                {live?.admin ? "Administrator" : "Standard user (service pausing & PresentMon limited)"}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

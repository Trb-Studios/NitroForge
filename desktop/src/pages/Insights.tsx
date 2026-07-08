// Insights hub: performance history, bottleneck analysis and the audit log.
import { useState } from "react";
import type { Live, Meta } from "../api";
import { Segmented } from "../components/ui";
import Analytics from "./Analytics";
import Bottleneck from "./Bottleneck";
import Logs from "./Logs";

const TABS = ["Analytics", "Bottleneck", "Logs"];

export default function Insights({ live }: { live: Live | null; meta?: Meta | null }) {
  const [tab, setTab] = useState("Analytics");
  return (
    <div className="space-y-5">
      <Segmented id="insights-tabs" options={TABS} value={tab} onChange={setTab} />
      {tab === "Analytics" && <Analytics live={live} />}
      {tab === "Bottleneck" && <Bottleneck live={live} />}
      {tab === "Logs" && <Logs live={live} />}
    </div>
  );
}

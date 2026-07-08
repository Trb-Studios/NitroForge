// Boost hub: the Booster config and the process manager in one place.
import { useState } from "react";
import type { Live, Meta } from "../api";
import { Segmented } from "../components/ui";
import Booster from "./Booster";
import Processes from "./Processes";

const TABS = ["Booster", "Processes"];

export default function Boost({ live }: { live: Live | null; meta?: Meta | null }) {
  const [tab, setTab] = useState("Booster");
  return (
    <div className="space-y-5">
      <Segmented id="boost-tabs" options={TABS} value={tab} onChange={setTab} />
      {tab === "Booster" ? <Booster live={live} /> : <Processes live={live} />}
    </div>
  );
}

// System hub: hardware specs, display resolution and the FPS overlay.
import { useState } from "react";
import type { Live, Meta } from "../api";
import { Segmented } from "../components/ui";
import OverlayPage from "./OverlayPage";
import Resolution from "./Resolution";
import Specs from "./Specs";

const TABS = ["PC Specs", "Resolution", "FPS Overlay"];

export default function System({ live }: { live: Live | null; meta?: Meta | null }) {
  const [tab, setTab] = useState("PC Specs");
  return (
    <div className="space-y-5">
      <Segmented id="system-tabs" options={TABS} value={tab} onChange={setTab} />
      {tab === "PC Specs" && <Specs live={live} />}
      {tab === "Resolution" && <Resolution live={live} />}
      {tab === "FPS Overlay" && <OverlayPage live={live} />}
    </div>
  );
}

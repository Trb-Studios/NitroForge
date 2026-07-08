// Typed client for the Python sidecar (see sidecar/server.py).
// The Rust shell hands us the ephemeral port + auth token via invoke.
import { invoke } from "@tauri-apps/api/core";
import { useEffect, useRef, useState } from "react";

let base = "";
let token = "";
let ready: Promise<void> | null = null;

export function initApi(): Promise<void> {
  if (!ready) {
    ready = invoke<{ port: number; token: string }>("get_sidecar_info").then(
      (i) => {
        base = `http://127.0.0.1:${i.port}/api`;
        token = i.token;
      },
    );
  }
  return ready;
}

export async function api<T = unknown>(path: string, body?: unknown): Promise<T> {
  await initApi();
  const res = await fetch(base + path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "X-FPSB-Token": token,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) throw new Error((data.error as string) ?? res.statusText);
  return data as T;
}

/** Poll a GET endpoint on an interval; null until first success. */
export function usePoll<T>(path: string, ms: number): T | null {
  const [data, setData] = useState<T | null>(null);
  const pathRef = useRef(path);
  pathRef.current = path;
  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const tick = async () => {
      try {
        const d = await api<T>(pathRef.current);
        if (alive) setData(d);
      } catch {
        /* sidecar still starting - retry */
      }
      if (alive) timer = window.setTimeout(tick, ms);
    };
    tick();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [path, ms]);
  return data;
}

// ------------------------------------------------------------------ types
export interface Live {
  cpu: number;
  ram: { percent: number; used_gb: number; total_gb: number };
  gpu: { load: number | null; mem_percent: number | null; temp: number | null };
  fps: { fps: number | null; frametime_ms: number | null; process: string | null };
  fps_running: boolean;
  net: { down_mbps: number; up_mbps: number; type: string; detail: string };
  boost: { active: boolean; changes: string[]; game: string | null };
  admin: boolean;
}

export interface ProcRow {
  pid: number;
  name: string;
  cpu: number;
  ram: number;
  disk_mbs: number;
  protected: boolean;
}

export interface Diagnostic {
  severity: "ok" | "warn" | "bad";
  text: string;
}

export interface GameInfo {
  name: string;
  exe: string;
  source: string;
  install_dir: string;
  fso_disabled: boolean;
}

export interface BoosterState {
  active: boolean;
  changes: string[];
  game: string | null;
  admin: boolean;
  flags: Record<string, boolean>;
  boost_on_launch: boolean;
  allowlist: string[];
  services: Record<string, string>;
}

export interface Finding {
  severity: "ok" | "warn" | "bad";
  title: string;
  detail: string;
}

export interface LogRecord {
  n: number;
  ts: number;
  level: string;
  msg: string;
}

export interface AnalyticsData {
  rows: { t: number; cpu: number | null; ram: number | null; gpu: number | null; fps: number | null; ft: number | null }[];
  stats: {
    avg_cpu: number | null;
    avg_gpu: number | null;
    avg_fps: number | null;
    min_fps: number | null;
    max_fps: number | null;
    avg_ram: number | null;
    count: number;
  };
}

export type Mode = [number, number, number]; // w, h, hz

export interface StartupApp {
  name: string;
  command: string;
  enabled: boolean;
}

// Friendly crash screen: catches any render error, reports it to the
// sidecar crash pipeline (local file + optional Discord/site delivery),
// and lets the user add context before sending.
import { Component, type ReactNode } from "react";
import { Flame, RefreshCw, Send } from "lucide-react";
import { api } from "../api";

interface State {
  error: Error | null;
  stack: string;
  feedback: string;
  sent: "idle" | "sending" | "done" | "failed";
}

export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null, stack: "", feedback: "", sent: "idle" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    const stack = `${error.stack ?? error.message}\n\nComponent stack:${info.componentStack ?? ""}`;
    this.setState({ stack });
    // always record locally, even if the user never clicks send
    api("/report/crash", {
      title: error.message || "UI crash",
      detail: stack,
      send: false,
    }).catch(() => {});
  }

  private sendReport = async () => {
    this.setState({ sent: "sending" });
    try {
      await api("/report/crash", {
        title: this.state.error?.message || "UI crash",
        detail: this.state.stack,
        feedback: this.state.feedback,
        send: true,
      });
      this.setState({ sent: "done" });
    } catch {
      this.setState({ sent: "failed" });
    }
  };

  render() {
    if (!this.state.error) return this.props.children;
    const { sent } = this.state;
    return (
      <div className="fixed inset-0 z-[95] flex items-center justify-center bg-bg p-8">
        <div className="w-[520px] max-w-full rounded-2xl bg-card ring-hair p-7">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-bad/15 flex items-center justify-center">
              <Flame size={18} className="text-bad" />
            </div>
            <div>
              <div className="text-[16px] font-bold">Something went wrong</div>
              <div className="text-[12px] text-mute">
                Nitro Forge hit an unexpected error. Your system was NOT left
                half-boosted - reverts run in the background engine.
              </div>
            </div>
          </div>

          <div className="rounded-xl bg-card2 p-3 max-h-32 overflow-y-auto mb-4">
            <pre className="text-[11px] text-ink2 whitespace-pre-wrap break-all">
              {this.state.error.message}
            </pre>
          </div>

          <div className="text-[12px] text-mute mb-1.5">
            What were you doing? (optional - sent with the report)
          </div>
          <textarea
            value={this.state.feedback}
            onChange={(e) => this.setState({ feedback: e.target.value })}
            className="w-full h-20 rounded-xl bg-card2 p-3 text-[12.5px] text-ink outline-none focus:ring-1 focus:ring-accent resize-none mb-4"
          />

          <div className="flex items-center gap-2">
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold bg-accent hover:bg-accent2 text-on-accent cursor-pointer flex items-center gap-2"
            >
              <RefreshCw size={14} /> Restart interface
            </button>
            <button
              onClick={this.sendReport}
              disabled={sent === "sending" || sent === "done"}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold bg-card2 hover:bg-[#232e3d] text-ink2 cursor-pointer flex items-center gap-2 disabled:opacity-50"
            >
              <Send size={14} />
              {sent === "done"
                ? "Report sent"
                : sent === "sending"
                  ? "Sending..."
                  : sent === "failed"
                    ? "Retry send"
                    : "Send crash report"}
            </button>
          </div>
          <div className="mt-3 text-[11px] text-mute">
            A diagnostic file was saved locally. Sending also delivers it to
            the channels configured in Settings → Reporting.
          </div>
        </div>
      </div>
    );
  }
}

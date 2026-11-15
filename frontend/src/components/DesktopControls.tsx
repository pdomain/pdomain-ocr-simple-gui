import type { ReactElement } from "react";
import { useMachine } from "@xstate/react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@pdomain/pdomain-ui/primitives";
import { apiFetch } from "../api/apiFetch";
import { desktopSessionMachine } from "../statecharts/desktopSessionMachine";

interface QuitResult {
  accepted: boolean;
  live_tabs: number;
  active_operations: number;
  message: string;
}

async function quitApp(
  confirmOtherTabs: boolean,
  pageId: string,
): Promise<QuitResult> {
  const response = await apiFetch("/api/lifecycle/browser-quit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      confirm_other_tabs: confirmOtherTabs,
      page_id: pageId,
    }),
  });
  if (!response.ok) throw new Error("Could not stop the app. Try again.");
  const body: unknown = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("accepted" in body) ||
    typeof body.accepted !== "boolean" ||
    !("live_tabs" in body) ||
    typeof body.live_tabs !== "number" ||
    !("active_operations" in body) ||
    typeof body.active_operations !== "number" ||
    !("message" in body) ||
    typeof body.message !== "string"
  )
    throw new Error("The app returned an invalid shutdown response.");
  return {
    accepted: body.accepted,
    live_tabs: body.live_tabs,
    active_operations: body.active_operations,
    message: body.message,
  };
}

export function DesktopControls(): ReactElement | null {
  const [session, send] = useMachine(desktopSessionMachine);
  const quit = useMutation({
    mutationFn: (confirmOtherTabs: boolean) =>
      quitApp(confirmOtherTabs, session.context.pageId),
    onSuccess: (result) => {
      if (result.accepted) send({ type: "quit" });
    },
  });
  if (session.matches("stopped")) {
    return <p role="status">App stopped. Open the app icon to start again.</p>;
  }
  if (session.context.instanceId === null) return null;
  return (
    <div className="desktop-controls" aria-label="App controls">
      {session.matches("retrying") && (
        <p role="status">
          Reconnecting. If the app stopped, open its app icon.
        </p>
      )}
      <Button
        size="sm"
        variant="outline"
        disabled={quit.isPending}
        onClick={() => quit.mutate(false)}
      >
        Quit app
      </Button>
      {quit.data && !quit.data.accepted && (
        <p role="alert">{quit.data.message}</p>
      )}
      {quit.error && <p role="alert">{quit.error.message}</p>}
      {quit.data &&
        !quit.data.accepted &&
        quit.data.active_operations === 0 &&
        quit.data.live_tabs > 1 && (
          <Button
            size="sm"
            variant="outline"
            disabled={quit.isPending}
            onClick={() => quit.mutate(true)}
          >
            Quit all tabs
          </Button>
        )}
    </div>
  );
}

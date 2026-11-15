import { assign, fromCallback, fromPromise, setup } from "xstate";
import { apiFetch } from "../api/apiFetch";

type Bootstrap = { managed: false } | { managed: true; instance_id: string };
type SessionEvent =
  { type: "connected" } | { type: "disconnected" } | { type: "quit" };
interface SessionContext {
  pageId: string;
  instanceId: string | null;
}
interface SocketInput {
  pageId: string;
  instanceId: string;
}

async function bootstrap(signal: AbortSignal): Promise<Bootstrap> {
  const response = await apiFetch("/api/lifecycle/bootstrap", {
    method: "POST",
    signal,
  });
  if (response.status === 404) return { managed: false };
  if (!response.ok) throw new Error("Could not connect to the app launcher");
  const body: unknown = await response.json();
  if (typeof body !== "object" || body === null || !("managed" in body)) {
    throw new Error("Invalid launcher response");
  }
  if (body.managed === false) return { managed: false };
  if (
    body.managed === true &&
    "instance_id" in body &&
    typeof body.instance_id === "string"
  ) {
    return { managed: true, instance_id: body.instance_id };
  }
  throw new Error("Invalid launcher instance identity");
}

export const desktopSessionMachine = setup({
  types: {
    context: {} as SessionContext,
    events: {} as SessionEvent,
  },
  actors: {
    bootstrap: fromPromise<Bootstrap>(({ signal }) => bootstrap(signal)),
    socket: fromCallback<SessionEvent, SocketInput>(({ input, sendBack }) => {
      const url = new URL("/api/lifecycle/session", window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      url.searchParams.set("instance_id", input.instanceId);
      url.searchParams.set("page_id", input.pageId);
      const socket = new WebSocket(url);
      let pendingShow: string | null = null;
      const acknowledgeFocus = () => {
        if (
          pendingShow !== null &&
          document.visibilityState === "visible" &&
          document.hasFocus() &&
          socket.readyState === WebSocket.OPEN
        ) {
          socket.send(
            JSON.stringify({ type: "show_ack", request_id: pendingShow }),
          );
          pendingShow = null;
        }
      };
      window.addEventListener("focus", acknowledgeFocus);
      document.addEventListener("visibilitychange", acknowledgeFocus);
      socket.onopen = () => sendBack({ type: "connected" });
      socket.onclose = () => sendBack({ type: "disconnected" });
      socket.onerror = () => socket.close();
      socket.onmessage = (event: MessageEvent<unknown>) => {
        if (typeof event.data !== "string") return;
        let message: unknown;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }
        if (
          typeof message === "object" &&
          message !== null &&
          "type" in message &&
          message.type === "show" &&
          "request_id" in message &&
          typeof message.request_id === "string"
        ) {
          pendingShow = message.request_id;
          window.focus();
          acknowledgeFocus();
        }
      };
      return () => {
        pendingShow = null;
        window.removeEventListener("focus", acknowledgeFocus);
        document.removeEventListener("visibilitychange", acknowledgeFocus);
        socket.onopen = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        socket.close();
      };
    }),
  },
}).createMachine({
  id: "desktopSession",
  context: () => ({ pageId: crypto.randomUUID(), instanceId: null }),
  initial: "bootstrapping",
  on: { quit: ".stopped" },
  states: {
    bootstrapping: {
      invoke: {
        src: "bootstrap",
        onDone: [
          {
            guard: ({ event }) => event.output.managed,
            target: "session",
            actions: assign({
              instanceId: ({ event }) =>
                event.output.managed ? event.output.instance_id : null,
            }),
          },
          { target: "inactive", actions: assign({ instanceId: null }) },
        ],
        onError: "retrying",
      },
    },
    session: {
      invoke: {
        src: "socket",
        onError: "retrying",
        input: ({ context }) => {
          if (context.instanceId === null)
            throw new Error("Missing launcher identity");
          return { pageId: context.pageId, instanceId: context.instanceId };
        },
      },
      initial: "connecting",
      states: {
        connecting: { on: { connected: "live" } },
        live: {},
      },
      on: { disconnected: "retrying" },
    },
    retrying: { after: { 1000: "bootstrapping" } },
    inactive: { type: "final" },
    stopped: { type: "final" },
  },
});

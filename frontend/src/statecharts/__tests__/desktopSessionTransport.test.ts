import { afterEach, describe, expect, it, vi } from "vitest";
import { createActor, fromPromise, waitFor } from "xstate";
import { desktopSessionMachine } from "../desktopSessionMachine";

class FakeSocket {
  static OPEN = 1;
  static instances: FakeSocket[] = [];
  readyState = 1;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<unknown>) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  url: URL;
  constructor(url: URL) {
    this.url = url;
    FakeSocket.instances.push(this);
  }
}

afterEach(() => {
  FakeSocket.instances = [];
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function actorWithSocket() {
  vi.stubGlobal("WebSocket", FakeSocket);
  return createActor(
    desktopSessionMachine.provide({
      actors: {
        bootstrap: fromPromise(async () => ({
          managed: true as const,
          instance_id: "instance-a",
        })),
      },
    }),
  );
}

describe("desktop socket ownership", () => {
  it("uses nonsecret identity parameters and releases handlers when stopped", async () => {
    const actor = actorWithSocket();
    try {
      actor.start();
      await waitFor(actor, (state) => state.matches("session"));
      const socket = FakeSocket.instances[0];
      expect(socket).toBeDefined();
      if (!socket) throw new Error("Missing session socket");
      expect(socket.url.pathname).toBe("/api/lifecycle/session");
      expect(socket.url.searchParams.get("instance_id")).toBe("instance-a");
      expect(socket.url.searchParams.has("token")).toBe(false);
      socket.onopen?.();
      expect(actor.getSnapshot().matches({ session: "live" })).toBe(true);
      actor.stop();
      expect(socket.close).toHaveBeenCalledTimes(1);
      expect(socket.onmessage).toBeNull();
      expect(socket.onclose).toBeNull();
    } finally {
      actor.stop();
    }
  });

  it.each(["visible", "hidden"] as const)(
    "acknowledges show only when the page is %s",
    async (visibility) => {
      vi.spyOn(document, "visibilityState", "get").mockReturnValue(visibility);
      vi.spyOn(document, "hasFocus").mockReturnValue(true);
      const focus = vi
        .spyOn(window, "focus")
        .mockImplementation(() => undefined);
      const actor = actorWithSocket();
      try {
        actor.start();
        await waitFor(actor, (state) => state.matches("session"));
        const socket = FakeSocket.instances[0];
        if (!socket) throw new Error("Missing session socket");
        socket.onmessage?.(
          new MessageEvent("message", {
            data: JSON.stringify({ type: "show", request_id: "show-1" }),
          }),
        );
        expect(focus).toHaveBeenCalledTimes(1);
        if (visibility === "visible") {
          expect(socket.send).toHaveBeenCalledWith(
            JSON.stringify({ type: "show_ack", request_id: "show-1" }),
          );
        } else {
          expect(socket.send).not.toHaveBeenCalled();
        }
        socket.onmessage?.(
          new MessageEvent("message", { data: "invalid json" }),
        );
        expect(focus).toHaveBeenCalledTimes(1);
      } finally {
        actor.stop();
      }
    },
  );

  it("waits for focus before acknowledging a visible background window", async () => {
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
    const focused = vi.spyOn(document, "hasFocus").mockReturnValue(false);
    vi.spyOn(window, "focus").mockImplementation(() => undefined);
    const actor = actorWithSocket();
    try {
      actor.start();
      await waitFor(actor, (state) => state.matches("session"));
      const socket = FakeSocket.instances[0];
      if (!socket) throw new Error("Missing session socket");
      socket.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({ type: "show", request_id: "focus-1" }),
        }),
      );
      expect(socket.send).not.toHaveBeenCalled();
      focused.mockReturnValue(true);
      window.dispatchEvent(new Event("focus"));
      expect(socket.send).toHaveBeenCalledWith(
        JSON.stringify({ type: "show_ack", request_id: "focus-1" }),
      );
    } finally {
      actor.stop();
    }
  });
});

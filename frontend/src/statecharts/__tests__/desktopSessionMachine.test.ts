import { afterEach, describe, expect, it, vi } from "vitest";
import { createActor, fromCallback, fromPromise, waitFor } from "xstate";
import { desktopSessionMachine } from "../desktopSessionMachine";

afterEach(() => vi.useRealTimers());

describe("desktop browser session", () => {
  it("clears desktop controls when reconnect finds a headless server", async () => {
    vi.useFakeTimers();
    let attempts = 0;
    const actor = createActor(
      desktopSessionMachine.provide({
        actors: {
          bootstrap: fromPromise(async () =>
            ++attempts === 1
              ? { managed: true as const, instance_id: "previous-instance" }
              : { managed: false as const },
          ),
          socket: fromCallback(({ sendBack }) => {
            sendBack({ type: "disconnected" });
          }),
        },
      }),
    );
    try {
      actor.start();
      await vi.advanceTimersByTimeAsync(1_000);
      expect(actor.getSnapshot().matches("inactive")).toBe(true);
      expect(actor.getSnapshot().context.instanceId).toBeNull();
    } finally {
      actor.stop();
    }
  });
  it("does not open a socket for a persistent headless server", async () => {
    const connect = vi.fn();
    const actor = createActor(
      desktopSessionMachine.provide({
        actors: {
          bootstrap: fromPromise(async () => ({ managed: false as const })),
          socket: fromCallback(connect),
        },
      }),
    );
    try {
      actor.start();
      await waitFor(actor, (state) => state.matches("inactive"));
      expect(connect).not.toHaveBeenCalled();
    } finally {
      actor.stop();
    }
  });

  it("uses distinct page identities and closes every owned connection", async () => {
    const cleanup = vi.fn();
    const ids: string[] = [];
    const machine = desktopSessionMachine.provide({
      actors: {
        bootstrap: fromPromise(async () => ({
          managed: true as const,
          instance_id: "instance-a",
        })),
        socket: fromCallback(({ input, sendBack }) => {
          ids.push(input.pageId);
          sendBack({ type: "connected" });
          return cleanup;
        }),
      },
    });
    const first = createActor(machine);
    const second = createActor(machine);
    try {
      first.start();
      second.start();
      await waitFor(first, (state) => state.matches({ session: "live" }));
      await waitFor(second, (state) => state.matches({ session: "live" }));
      expect(ids).toHaveLength(2);
      expect(ids[0]).not.toBe(ids[1]);
    } finally {
      first.stop();
      second.stop();
    }
    expect(cleanup).toHaveBeenCalledTimes(2);
  });

  it("cancels reconnect work when the page closes", async () => {
    vi.useFakeTimers();
    const bootstrap = vi.fn(async () => ({
      managed: true as const,
      instance_id: "instance-a",
    }));
    const cleanup = vi.fn();
    const actor = createActor(
      desktopSessionMachine.provide({
        actors: {
          bootstrap: fromPromise(bootstrap),
          socket: fromCallback(({ sendBack }) => {
            sendBack({ type: "disconnected" });
            return cleanup;
          }),
        },
      }),
    );
    try {
      actor.start();
      await vi.advanceTimersByTimeAsync(0);
      expect(actor.getSnapshot().matches("retrying")).toBe(true);
      actor.stop();
      await vi.advanceTimersByTimeAsync(10_000);
      expect(bootstrap).toHaveBeenCalledTimes(1);
      expect(cleanup).toHaveBeenCalledTimes(1);
    } finally {
      actor.stop();
    }
  });

  it("bootstraps a fresh server identity after reconnect", async () => {
    vi.useFakeTimers();
    let attempt = 0;
    const identities: string[] = [];
    const actor = createActor(
      desktopSessionMachine.provide({
        actors: {
          bootstrap: fromPromise(async () => ({
            managed: true as const,
            instance_id: `instance-${++attempt}`,
          })),
          socket: fromCallback(({ input, sendBack }) => {
            identities.push(input.instanceId);
            if (identities.length === 1) sendBack({ type: "disconnected" });
            else sendBack({ type: "connected" });
          }),
        },
      }),
    );
    try {
      actor.start();
      await vi.advanceTimersByTimeAsync(1_000);
      expect(identities).toEqual(["instance-1", "instance-2"]);
      expect(actor.getSnapshot().matches({ session: "live" })).toBe(true);
    } finally {
      actor.stop();
    }
  });
});

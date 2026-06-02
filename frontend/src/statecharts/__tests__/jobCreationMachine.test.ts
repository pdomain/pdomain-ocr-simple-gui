import { createActor, fromPromise, waitFor } from "xstate";
import { describe, expect, it } from "vitest";
import { jobCreationMachine } from "../jobCreationMachine";
import type { ChosenSource, JobForm } from "../jobCreationTypes";

function startMachine(config: {
  mode: "local" | "managed";
  is_containerized: boolean;
}) {
  const actor = createActor(
    jobCreationMachine.provide({
      actors: {
        loadConfig: fromPromise(async () => ({
          ...config,
          detected_device: "cpu",
          gpu_available: false,
          ocr_engines: [
            { id: "doctr", label: "DocTR", available: true, reason: null },
            {
              id: "tesseract",
              label: "Tesseract",
              available: true,
              reason: null,
            },
          ],
        })),
        uploadFiles: fromPromise(async () => ({ uploadId: "upload-123" })),
        createJob: fromPromise(async () => ({ projectId: "job-123" })),
      },
    }),
  );
  actor.start();
  return actor;
}

describe("jobCreationMachine runtime profiles", () => {
  // Machine-Covers: B-HOME-014
  it("enters localHost when local and not containerized", async () => {
    const actor = startMachine({ mode: "local", is_containerized: false });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localHost" }),
    );
    expect(actor.getSnapshot().context.profile?.kind).toBe("local-host");
    actor.stop();
  });

  it("enters localContainer when local and containerized", async () => {
    const actor = startMachine({ mode: "local", is_containerized: true });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localContainer" }),
    );
    expect(actor.getSnapshot().context.profile?.kind).toBe("local-container");
    actor.stop();
  });

  it("enters managedServer and rejects path sources in managed mode", async () => {
    const actor = startMachine({ mode: "managed", is_containerized: false });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "managedServer" }),
    );
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    expect(
      actor.getSnapshot().matches({ choosingSource: "managedServer" }),
    ).toBe(true);
    expect(actor.getSnapshot().context.source).toBeNull();
    actor.stop();
  });
});

describe("jobCreationMachine flow", () => {
  // Machine-Covers: B-HOME-002
  it("uploads files, stores the upload source, and emits behavior trace", async () => {
    const actor = startMachine({ mode: "local", is_containerized: true });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localContainer" }),
    );
    actor.send({
      type: "FILES_SELECTED",
      files: [new File(["x"], "scan.png")],
    });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    expect(actor.getSnapshot().context.source).toEqual({
      kind: "upload",
      uploadId: "upload-123",
    });
    expect(actor.getSnapshot().context.behaviorTrace).toContain("B-HOME-002");
    actor.stop();
  });

  // Machine-Covers: B-HOME-003 B-HOME-011
  it("submits a job and stores the returned project id", async () => {
    const actor = startMachine({ mode: "local", is_containerized: false });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localHost" }),
    );
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    actor.send({ type: "SUBMIT_JOB" });
    await waitFor(actor, (state) => state.matches("submitted"));
    expect(actor.getSnapshot().context.submittedProjectId).toBe("job-123");
    expect(actor.getSnapshot().context.behaviorTrace).toContain("B-HOME-011");
    actor.stop();
  });

  it("submits the final form payload from the submit event", async () => {
    const createInputs: Array<{ source: ChosenSource; jobForm: JobForm }> = [];
    const actor = createActor(
      jobCreationMachine.provide({
        actors: {
          loadConfig: fromPromise(async () => ({
            mode: "local",
            is_containerized: false,
            detected_device: "local",
            gpu_available: true,
            ocr_engines: [
              { id: "doctr", label: "DocTR", available: true, reason: null },
              {
                id: "tesseract",
                label: "Tesseract",
                available: true,
                reason: null,
              },
            ],
          })),
          uploadFiles: fromPromise(async () => ({ uploadId: "upload-123" })),
          createJob: fromPromise(
            async ({
              input,
            }: {
              input: { source: ChosenSource; jobForm: JobForm };
            }) => {
              createInputs.push(input);
              return { projectId: "job-123" };
            },
          ),
        },
      }),
    );
    actor.start();
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localHost" }),
    );
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    actor.send({
      type: "SUBMIT_JOB",
      jobForm: {
        name: "edited scans",
        engine: "tesseract",
        language: "fr",
        straight_quotes: false,
        em_dash_to_double_hyphen: false,
        emit_illustration_placeholders: true,
        device: "gpu",
        batch_pages: 3,
        output: { mode: "specified", path: "/tmp/out" },
      },
    });
    await waitFor(actor, (state) => state.matches("submitted"));

    expect(createInputs[0]).toMatchObject({
      source: { kind: "path", path: "/tmp/scans" },
      jobForm: {
        name: "edited scans",
        engine: "tesseract",
        language: "fr",
        straight_quotes: false,
        em_dash_to_double_hyphen: false,
        emit_illustration_placeholders: true,
        device: "gpu",
        batch_pages: 3,
        output: { mode: "specified", path: "/tmp/out" },
      },
    });
    actor.stop();
  });

  it("normalizes an unavailable submitted engine before creating the job", async () => {
    const createInputs: Array<{ source: ChosenSource; jobForm: JobForm }> = [];
    const actor = createActor(
      jobCreationMachine.provide({
        actors: {
          loadConfig: fromPromise(async () => ({
            mode: "local" as const,
            is_containerized: false,
            detected_device: "cpu",
            gpu_available: false,
            ocr_engines: [
              { id: "doctr", label: "DocTR", available: true, reason: null },
              {
                id: "tesseract",
                label: "Tesseract",
                available: false,
                reason: "Tesseract language data is unavailable.",
              },
            ],
          })),
          uploadFiles: fromPromise(async () => ({ uploadId: "upload-123" })),
          createJob: fromPromise(
            async ({
              input,
            }: {
              input: { source: ChosenSource; jobForm: JobForm };
            }) => {
              createInputs.push(input);
              return { projectId: "job-123" };
            },
          ),
        },
      }),
    );
    actor.start();
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localHost" }),
    );
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    actor.send({
      type: "SUBMIT_JOB",
      jobForm: {
        name: "edited scans",
        engine: "tesseract",
        language: "en",
        straight_quotes: true,
        em_dash_to_double_hyphen: true,
        emit_illustration_placeholders: false,
        device: "auto",
        batch_pages: null,
        output: { mode: "managed" },
      },
    });
    await waitFor(actor, (state) => state.matches("submitted"));

    expect(createInputs[0].jobForm.engine).toBe("doctr");
    actor.stop();
  });

  it("preserves source and form context when submit fails", async () => {
    const actor = createActor(
      jobCreationMachine.provide({
        actors: {
          loadConfig: fromPromise(async () => ({
            mode: "local",
            is_containerized: false,
            detected_device: "cpu",
            gpu_available: false,
            ocr_engines: [
              { id: "doctr", label: "DocTR", available: true, reason: null },
              {
                id: "tesseract",
                label: "Tesseract",
                available: true,
                reason: null,
              },
            ],
          })),
          uploadFiles: fromPromise(async () => ({ uploadId: "upload-123" })),
          createJob: fromPromise(async () => {
            throw new Error("bad request");
          }),
        },
      }),
    );
    actor.start();
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localHost" }),
    );
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    actor.send({
      type: "JOB_FORM_CHANGED",
      patch: { name: "scans", language: "fr" },
    });
    actor.send({ type: "SUBMIT_JOB" });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    expect(actor.getSnapshot().context.source).toEqual({
      kind: "path",
      path: "/tmp/scans",
    });
    expect(actor.getSnapshot().context.jobForm.language).toBe("fr");
    expect(actor.getSnapshot().context.submitError).toContain("bad request");
    actor.stop();
  });
});

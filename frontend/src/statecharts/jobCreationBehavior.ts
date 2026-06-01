export const JOB_CREATION_BEHAVIOR = {
  uploadViaDropOrPicker: "B-HOME-002",
  chooseLocalPath: "B-HOME-003",
  clearSource: "B-HOME-004",
  configFailure: "B-HOME-014",
  submitJob: "B-HOME-011",
} as const;

export type JobCreationBehaviorId =
  (typeof JOB_CREATION_BEHAVIOR)[keyof typeof JOB_CREATION_BEHAVIOR];

export function appendBehaviorTrace(
  trace: string[],
  id: JobCreationBehaviorId,
): string[] {
  return trace.includes(id) ? trace : [...trace, id];
}

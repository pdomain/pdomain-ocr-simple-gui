// Tests for SourcePicker — A6.2
import { fireEvent, render, screen } from "@testing-library/react";
import { SourcePicker } from "../SourcePicker";

it("calls onUploadComplete for a dropped file", async () => {
  const onUploadComplete = vi.fn();
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({ upload_id: "u1" }),
  })) as unknown as typeof fetch;
  render(
    <SourcePicker
      allowDrop
      allowFilePick
      allowPathInput
      onUploadComplete={onUploadComplete}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(drop, { dataTransfer: { files: [file] } });
  await vi.waitFor(() => expect(onUploadComplete).toHaveBeenCalledWith("u1"));
});

it("emits onPathChosen for path input", () => {
  const onPathChosen = vi.fn();
  render(
    <SourcePicker
      allowDrop={false}
      allowFilePick={false}
      allowPathInput
      onUploadComplete={() => {}}
      onPathChosen={onPathChosen}
      pathHint="Folder, image, or zip path"
    />,
  );
  const input = screen.getByTestId("source-picker-path-input");
  fireEvent.change(input, { target: { value: "/scans/book1" } });
  fireEvent.submit(input.closest("form")!);
  expect(onPathChosen).toHaveBeenCalledWith("/scans/book1");
});

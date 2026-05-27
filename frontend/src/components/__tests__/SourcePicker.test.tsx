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

it("renders a visible Choose files button that triggers the hidden input", () => {
  render(
    <SourcePicker
      allowDrop={false}
      allowFilePick
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const button = screen.getByRole("button", { name: /choose files/i });
  expect(button).toBeInTheDocument();
  const input = screen.getByTestId("source-picker-file-pick") as HTMLInputElement;
  // The native input should be visually hidden (sr-only / opacity:0 / clip).
  expect(input.className).toMatch(/sr-only|visually-hidden/);
  const clickSpy = vi.spyOn(input, "click");
  fireEvent.click(button);
  expect(clickSpy).toHaveBeenCalled();
});

it("shows an error message when upload fails", async () => {
  globalThis.fetch = (async () => ({
    ok: false,
    status: 500,
    json: async () => ({}),
  })) as unknown as typeof fetch;
  render(
    <SourcePicker
      allowDrop
      allowFilePick
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(drop, { dataTransfer: { files: [file] } });
  const errEl = await screen.findByTestId("source-picker-error");
  expect(errEl.textContent ?? "").toMatch(/upload/i);
});

it("dropzone toggles a drag-active state on dragenter/dragleave", () => {
  render(
    <SourcePicker
      allowDrop
      allowFilePick={false}
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  expect(drop.getAttribute("data-drag-active")).toBe("false");
  fireEvent.dragEnter(drop);
  expect(drop.getAttribute("data-drag-active")).toBe("true");
  fireEvent.dragLeave(drop);
  expect(drop.getAttribute("data-drag-active")).toBe("false");
});

it("dropzone has a generous min-height", () => {
  render(
    <SourcePicker
      allowDrop
      allowFilePick={false}
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop") as HTMLElement;
  // Style is applied inline; parse the minHeight attribute.
  const minHeight = drop.style.minHeight;
  expect(minHeight).toBeTruthy();
  const value = parseInt(minHeight, 10);
  expect(value).toBeGreaterThanOrEqual(100);
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

// Tests for SourcePicker — A6.2
import { fireEvent, render, screen } from "@testing-library/react";
import { SourcePicker } from "../SourcePicker";

function mockUploadFetch(uploadId = "u1") {
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({ upload_id: uploadId }),
  })) as unknown as typeof fetch;
}

it("calls onUploadComplete for a dropped file", async () => {
  const onUploadComplete = vi.fn();
  mockUploadFetch("u1");
  render(
    <SourcePicker
      allowDrop
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

it("clicking the dropzone triggers the hidden file input", () => {
  mockUploadFetch();
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  render(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  fireEvent.click(drop);
  expect(clickSpy).toHaveBeenCalled();
  clickSpy.mockRestore();
});

it("pressing Enter on the dropzone triggers the file input", () => {
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  render(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  fireEvent.keyDown(drop, { key: "Enter" });
  expect(clickSpy).toHaveBeenCalled();
  clickSpy.mockRestore();
});

it("renders the dropped filename after a drop", async () => {
  mockUploadFetch("u2");
  render(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  const file = new File(["x"], "scan-007.png", { type: "image/png" });
  fireEvent.drop(drop, { dataTransfer: { files: [file] } });
  expect(
    await screen.findByTestId("source-picker-chosen"),
  ).toHaveTextContent("scan-007.png");
});

it("renders +N more for multiple dropped files", async () => {
  mockUploadFetch();
  render(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  const files = [
    new File(["a"], "a.png", { type: "image/png" }),
    new File(["b"], "b.png", { type: "image/png" }),
    new File(["c"], "c.png", { type: "image/png" }),
  ];
  fireEvent.drop(drop, { dataTransfer: { files } });
  const chosen = await screen.findByTestId("source-picker-chosen");
  expect(chosen.textContent).toContain("a.png");
  expect(chosen.textContent).toContain("(+2 more)");
});

it("clear button resets the display and fires onClear", async () => {
  mockUploadFetch();
  const onClear = vi.fn();
  render(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
      onClear={onClear}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(drop, { dataTransfer: { files: [file] } });
  const clearBtn = await screen.findByTestId("source-picker-clear");
  fireEvent.click(clearBtn);
  expect(onClear).toHaveBeenCalled();
  expect(screen.queryByTestId("source-picker-chosen")).toBeNull();
});

it("clicking the clear button does not re-open the file picker", async () => {
  mockUploadFetch();
  const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click");
  render(
    <SourcePicker
      allowDrop
      allowPathInput={false}
      onUploadComplete={() => {}}
      onPathChosen={() => {}}
    />,
  );
  const drop = screen.getByTestId("source-picker-drop");
  const file = new File(["x"], "scan.png", { type: "image/png" });
  fireEvent.drop(drop, { dataTransfer: { files: [file] } });
  const clearBtn = await screen.findByTestId("source-picker-clear");
  clickSpy.mockClear();
  fireEvent.click(clearBtn);
  expect(clickSpy).not.toHaveBeenCalled();
  clickSpy.mockRestore();
});

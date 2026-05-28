// OutputConfigPanel tests — A7.1
import { fireEvent, render, screen } from "@testing-library/react";
import { OutputConfigPanel } from "../OutputConfigPanel";

it("disables next_to_source when source is not a folder", () => {
  render(
    <OutputConfigPanel
      mode="local"
      sourceIsFolder={false}
      value={{ mode: "managed" }}
      onChange={() => {}}
    />,
  );
  expect(screen.getByTestId("output-mode-next-to-source")).toBeDisabled();
});

it("disables specified in managed mode", () => {
  render(
    <OutputConfigPanel
      mode="managed"
      sourceIsFolder={false}
      value={{ mode: "managed" }}
      onChange={() => {}}
    />,
  );
  expect(screen.getByTestId("output-mode-specified")).toBeDisabled();
});

it("emits change when path is typed in specified mode", () => {
  const onChange = vi.fn();
  render(
    <OutputConfigPanel
      mode="local"
      sourceIsFolder
      value={{ mode: "specified", path: "" }}
      onChange={onChange}
    />,
  );
  const input = screen.getByTestId("output-specified-path");
  fireEvent.change(input, { target: { value: "/out" } });
  expect(onChange).toHaveBeenLastCalledWith({
    mode: "specified",
    path: "/out",
  });
});

it("emits change with empty path when path input is cleared", () => {
  const onChange = vi.fn();
  render(
    <OutputConfigPanel
      mode="local"
      sourceIsFolder
      value={{ mode: "specified", path: "/existing" }}
      onChange={onChange}
    />,
  );
  const input = screen.getByTestId("output-specified-path");
  fireEvent.change(input, { target: { value: "" } });
  expect(onChange).toHaveBeenLastCalledWith({
    mode: "specified",
    path: "",
  });
});

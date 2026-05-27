// PageViewerWithZoom — wraps ArtifactViewer with a CSS-transform zoom layer
// and a fit-to-page default.
//
// Why a wrapper: pdomain-ui's ArtifactViewer (v0.2.2) has no zoom prop — it
// renders Konva at the literal pageWidth × pageHeight, which is "too zoomed
// in" for high-DPI scans (e.g. a 2609px-tall jp2). A CSS scale on the
// containing div is the simplest way to fit-to-container without touching
// the upstream component.

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

const ZOOM_MIN = 0.1;
const ZOOM_MAX = 4;
const ZOOM_STEP_IN = 1.25;
const ZOOM_STEP_OUT = 0.8;

interface ZoomState {
  zoom: number;
  fitZoom: number;
}

export interface ZoomHandle {
  /** Current zoom factor (1.0 = native). */
  getZoom: () => number;
  /** Fit-to-container zoom factor as last computed. */
  getFitZoom: () => number;
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  reset100: () => void;
  /** Imperatively set zoom (clamped). Exposed for tests. */
  setZoom: (z: number) => void;
}

export interface PageViewerWithZoomProps {
  pageWidth: number;
  pageHeight: number;
  /** ArtifactViewer (or test mock) element to wrap. */
  children: ReactNode;
  /**
   * Override the measured container size — only the tests use this so they
   * don't have to mock layout. Production code should leave it undefined.
   */
  measuredSize?: { width: number; height: number };
  onZoomChange?: (state: ZoomState) => void;
}

function clamp(z: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
}

function computeFit(cw: number, ch: number, pw: number, ph: number): number {
  if (cw <= 0 || ch <= 0 || pw <= 0 || ph <= 0) return 1;
  return Math.min(cw / pw, ch / ph);
}

export const PageViewerWithZoom = forwardRef<
  ZoomHandle,
  PageViewerWithZoomProps
>(function PageViewerWithZoom(
  { pageWidth, pageHeight, children, measuredSize, onZoomChange },
  ref,
) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState<{
    width: number;
    height: number;
  }>({ width: 0, height: 0 });
  const [zoom, setZoomState] = useState<number>(1);
  const [autoFit, setAutoFit] = useState<boolean>(true);

  // Observe viewport size so fit zoom updates on resize.
  useLayoutEffect(() => {
    if (measuredSize) {
      setContainerSize(measuredSize);
      return;
    }
    const el = viewportRef.current;
    if (!el) return;
    const update = () => {
      setContainerSize({ width: el.clientWidth, height: el.clientHeight });
    };
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      ro.disconnect();
    };
  }, [measuredSize]);

  const fitZoom = computeFit(
    containerSize.width,
    containerSize.height,
    pageWidth,
    pageHeight,
  );

  // Keep zoom snapped to fit while the user hasn't manually overridden it.
  useEffect(() => {
    if (autoFit) {
      setZoomState(fitZoom);
    }
  }, [autoFit, fitZoom]);

  useEffect(() => {
    onZoomChange?.({ zoom, fitZoom });
  }, [zoom, fitZoom, onZoomChange]);

  const applyZoom = useCallback((next: number) => {
    setAutoFit(false);
    setZoomState(clamp(next));
  }, []);

  const zoomIn = useCallback(() => {
    setAutoFit(false);
    setZoomState((z) => clamp(z * ZOOM_STEP_IN));
  }, []);
  const zoomOut = useCallback(() => {
    setAutoFit(false);
    setZoomState((z) => clamp(z * ZOOM_STEP_OUT));
  }, []);
  const fit = useCallback(() => {
    setAutoFit(true);
    setZoomState(fitZoom);
  }, [fitZoom]);
  const reset100 = useCallback(() => {
    setAutoFit(false);
    setZoomState(1);
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      getZoom: () => zoom,
      getFitZoom: () => fitZoom,
      zoomIn,
      zoomOut,
      fit,
      reset100,
      setZoom: applyZoom,
    }),
    [zoom, fitZoom, zoomIn, zoomOut, fit, reset100, applyZoom],
  );

  return (
    <div
      ref={viewportRef}
      data-testid="page-zoom-viewport"
      data-zoom={zoom.toFixed(4)}
      data-fit-zoom={fitZoom.toFixed(4)}
      data-auto-fit={autoFit ? "true" : "false"}
      style={{
        width: "100%",
        height: "100%",
        overflow: "auto",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          width: pageWidth * zoom,
          height: pageHeight * zoom,
          position: "relative",
          flex: "none",
        }}
      >
        <div
          style={{
            width: pageWidth,
            height: pageHeight,
            transform: `scale(${zoom})`,
            transformOrigin: "top left",
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
});

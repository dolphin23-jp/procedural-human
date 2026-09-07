import {
  ThreeFixtureRenderer,
  createFixtureCoordinateTransform,
} from '@procedural-human/rendering-three';
import { useEffect, useRef, useState } from 'react';

export function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [selectedStructure, setSelectedStructure] = useState<string | null>(
    null,
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let renderer: ThreeFixtureRenderer;
    try {
      renderer = new ThreeFixtureRenderer(canvas, {
        coordinates: createFixtureCoordinateTransform(),
      });
      renderer.attachInput({
        onSelection: (selection) =>
          setSelectedStructure(selection?.anatomicalEntity.name ?? null),
      });
    } catch (error) {
      setRenderError(
        error instanceof Error
          ? error.message
          : 'Unable to initialize 3D view.',
      );
      return;
    }
    const resize = () => {
      const { width, height } = canvas.getBoundingClientRect();
      if (width > 0 && height > 0) renderer.resize(width, height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    return () => {
      observer.disconnect();
      renderer.dispose();
    };
  }, []);

  return (
    <main className="shell">
      <section className="viewer" aria-labelledby="app-title">
        <header className="viewer__header">
          <div>
            <p className="viewer__eyebrow">M4 · 3D Runtime</p>
            <h1 id="app-title">Synthetic anatomy fixture</h1>
          </div>
          <p className="viewer__notice">
            Development fixture · not medical anatomy
          </p>
        </header>
        <div className="viewer__viewport">
          <canvas ref={canvasRef} aria-label="3D synthetic anatomy fixture" />
          <p className="viewer__controls">
            Drag to rotate · Shift-drag to pan · wheel/pinch to zoom · tap to
            select
          </p>
          {selectedStructure && (
            <p className="viewer__selection" aria-live="polite">
              Selected: {selectedStructure}
            </p>
          )}
          <div className="viewer__legend" aria-label="Fixture structure legend">
            <span>
              <i className="legend-swatch legend-swatch--skin" />
              Skin
            </span>
            <span>
              <i className="legend-swatch legend-swatch--tissue" />
              Soft tissue
            </span>
            <span>
              <i className="legend-swatch legend-swatch--vein" />
              Vein
            </span>
            <span>
              <i className="legend-swatch legend-swatch--artery" />
              Artery
            </span>
          </div>
          {renderError && (
            <p className="viewer__error">3D view unavailable: {renderError}</p>
          )}
        </div>
      </section>
    </main>
  );
}

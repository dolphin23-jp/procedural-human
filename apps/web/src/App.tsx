import {
  CornerstoneAxialVolumeViewer,
  createSyntheticAxialVolumeFixture,
  type AxialSliceState,
} from '@procedural-human/imaging-cornerstone';
import {
  ThreeFixtureRenderer,
  createFixtureCoordinateTransform,
  createFixtureDemoClippingPlane,
  type SemanticPickResult,
} from '@procedural-human/rendering-three';
import { useEffect, useRef, useState } from 'react';

const imagingFixture = createSyntheticAxialVolumeFixture();

const accuracyRows = [
  ['Identity', 'identityAccuracy'],
  ['Topology', 'topologyAccuracy'],
  ['Geometry', 'geometryAccuracy'],
  ['Registration', 'registrationAccuracy'],
  ['Diameter', 'diameterAccuracy'],
  ['Relationship', 'relationshipAccuracy'],
] as const;

function metadataValue(value: string | null): string {
  return value ?? 'Unavailable';
}

function StructureMetadataPanel({
  selection,
}: {
  readonly selection: SemanticPickResult;
}) {
  const entity = selection.anatomicalEntity;

  return (
    <aside className="viewer__metadata" aria-label="Structure metadata">
      <p className="metadata__eyebrow">Selected structure</p>
      <h2>{entity.name}</h2>
      <dl className="metadata__summary">
        <dt>Source class</dt>
        <dd>{entity.provenance.sourceClass}</dd>
        <dt>Validation</dt>
        <dd>{entity.validation.level}</dd>
      </dl>
      {entity.validation.notes && (
        <p className="metadata__notes">{entity.validation.notes}</p>
      )}
      <h3>Accuracy</h3>
      <dl className="metadata__accuracy">
        {accuracyRows.map(([label, key]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{metadataValue(entity.accuracy[key])}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}

function ImagingPanel() {
  const elementRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<CornerstoneAxialVolumeViewer | null>(null);
  const [slice, setSlice] = useState<AxialSliceState | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    let cancelled = false;
    let observer: ResizeObserver | null = null;

    void CornerstoneAxialVolumeViewer.create(element, imagingFixture)
      .then((viewer) => {
        if (cancelled) {
          viewer.dispose();
          return;
        }
        viewerRef.current = viewer;
        setSlice(viewer.currentSlice);
        observer = new ResizeObserver(() => viewer.resize());
        observer.observe(element);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setImageError(
            error instanceof Error
              ? error.message
              : 'Unable to initialize imaging view.',
          );
        }
      });

    return () => {
      cancelled = true;
      observer?.disconnect();
      const viewer = viewerRef.current;
      viewerRef.current = null;
      viewer?.dispose();
    };
  }, []);

  const moveSlice = async (displayIndex: number) => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    try {
      setSlice(await viewer.setSlice(displayIndex));
      setImageError(null);
    } catch (error) {
      setImageError(
        error instanceof Error ? error.message : 'Unable to move image slice.',
      );
    }
  };

  const origin = slice?.plane.origin.value;

  return (
    <section className="imaging" aria-labelledby="imaging-title">
      <header className="viewer__header">
        <div>
          <p className="viewer__eyebrow">M5 · Medical Imaging Bridge</p>
          <h2 id="imaging-title">Synthetic axial calibration volume</h2>
        </div>
        <p className="viewer__notice">Development fixture · not medical imaging</p>
      </header>
      <div className="imaging__body">
        <div
          ref={elementRef}
          className="imaging__viewport"
          aria-label="Cornerstone axial development image viewport"
        />
        <div className="imaging__controls">
          <label htmlFor="axial-slice">Axial slice</label>
          <input
            id="axial-slice"
            type="range"
            min={0}
            max={imagingFixture.frame.dimensions.k - 1}
            step={1}
            value={slice?.displayIndex ?? 0}
            disabled={!slice}
            onChange={(event) => void moveSlice(Number(event.target.value))}
          />
          <span>
            {slice ? slice.displayIndex + 1 : '–'} /{' '}
            {imagingFixture.frame.dimensions.k}
          </span>
        </div>
        <dl className="imaging__position" aria-label="Patient-space slice position">
          <div>
            <dt>Source voxel k</dt>
            <dd>{slice?.voxelK ?? '–'}</dd>
          </div>
          <div>
            <dt>Patient plane origin</dt>
            <dd>
              {origin
                ? `(${origin.x.toFixed(1)}, ${origin.y.toFixed(1)}, ${origin.z.toFixed(1)}) mm`
                : '–'}
            </dd>
          </div>
        </dl>
        <p className="imaging__provenance">
          {imagingFixture.provenance.validationLevel} ·{' '}
          {imagingFixture.provenance.notes}
        </p>
        {imageError && (
          <p className="imaging__error">Imaging view unavailable: {imageError}</p>
        )}
      </div>
    </section>
  );
}

export function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<ThreeFixtureRenderer | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [selection, setSelection] = useState<SemanticPickResult | null>(null);
  const [clippingEnabled, setClippingEnabled] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let renderer: ThreeFixtureRenderer;
    try {
      renderer = new ThreeFixtureRenderer(canvas, {
        coordinates: createFixtureCoordinateTransform(),
      });
      rendererRef.current = renderer;
      renderer.attachInput({
        onSelection: setSelection,
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
      if (rendererRef.current === renderer) rendererRef.current = null;
      renderer.dispose();
    };
  }, []);

  const toggleClipping = () => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    const enabled = !clippingEnabled;
    renderer.setClippingPlane(
      enabled ? createFixtureDemoClippingPlane() : null,
    );
    setClippingEnabled(enabled);
  };

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
          <button
            className="viewer__clip-toggle"
            type="button"
            aria-pressed={clippingEnabled}
            onClick={toggleClipping}
          >
            Clipping plane: {clippingEnabled ? 'On' : 'Off'}
          </button>
          {selection && <StructureMetadataPanel selection={selection} />}
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
      <ImagingPanel />
    </main>
  );
}

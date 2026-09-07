import {
  CornerstoneAxialVolumeViewer,
  createSyntheticAxialVolumeFixture,
  type AxialSliceState,
} from '@procedural-human/imaging-cornerstone';
import {
  ThreeFixtureRenderer,
  createFixtureCoordinateTransform,
  type SemanticPickResult,
} from '@procedural-human/rendering-three';
import {
  ImagingPlaneSynchronizer,
  type ImagingPlaneSyncState,
} from '@procedural-human/session';
import { useEffect, useRef, useState, type RefObject } from 'react';

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

function ImagingPanel({
  elementRef,
  slice,
  imageError,
  moveSlice,
  scrollImage,
}: {
  elementRef: RefObject<HTMLDivElement | null>;
  slice: AxialSliceState | null;
  imageError: string | null;
  moveSlice: (index: number) => void;
  scrollImage: (delta: number) => void;
}) {
  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey && event.deltaY !== 0) {
        event.preventDefault();
        scrollImage(Math.sign(event.deltaY));
      }
    };
    element.addEventListener('wheel', wheel, { passive: false });
    return () => element.removeEventListener('wheel', wheel);
  }, [elementRef, scrollImage]);

  const origin = slice?.plane.origin.value;

  return (
    <section className="imaging" aria-labelledby="imaging-title">
      <header className="viewer__header">
        <div>
          <p className="viewer__eyebrow">M5 · Medical Imaging Bridge</p>
          <h2 id="imaging-title">Synthetic axial calibration volume</h2>
        </div>
        <p className="viewer__notice">
          Development fixture · not medical imaging
        </p>
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
            disabled={!slice && !imageError}
            onChange={(event) => void moveSlice(Number(event.target.value))}
          />
          <span>
            {slice ? slice.displayIndex + 1 : '–'} /{' '}
            {imagingFixture.frame.dimensions.k}
          </span>
        </div>
        <dl
          className="imaging__position"
          aria-label="Patient-space slice position"
        >
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
          <p className="imaging__error">
            Imaging view unavailable: {imageError}
          </p>
        )}
      </div>
    </section>
  );
}

export function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageElementRef = useRef<HTMLDivElement>(null);
  const syncRef = useRef<ImagingPlaneSynchronizer | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [selection, setSelection] = useState<SemanticPickResult | null>(null);
  const [syncState, setSyncState] = useState<ImagingPlaneSyncState | null>(
    null,
  );
  const slice = syncState?.slice ?? null;
  const clippingEnabled = syncState?.clippingEnabled ?? true;

  useEffect(() => {
    const canvas = canvasRef.current;
    const element = imageElementRef.current;
    if (!canvas || !element) return;
    let cancelled = false;
    let viewer: CornerstoneAxialVolumeViewer | null = null;
    let synchronizer: ImagingPlaneSynchronizer | null = null;
    let imageObserver: ResizeObserver | null = null;
    let renderer: ThreeFixtureRenderer;
    try {
      renderer = new ThreeFixtureRenderer(canvas, {
        coordinates: createFixtureCoordinateTransform(),
      });
      renderer.attachInput({ onSelection: setSelection });
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

    // Defer creation past StrictMode's first cleanup; late completions own only
    // their local viewer and cannot dispose a newer mount's resources.
    void Promise.resolve().then(async () => {
      if (cancelled) return;
      try {
        const created = await CornerstoneAxialVolumeViewer.create(
          element,
          imagingFixture,
        );
        if (cancelled) {
          created.dispose();
          return;
        }
        viewer = created;
        synchronizer = new ImagingPlaneSynchronizer({
          image: created,
          render: renderer,
          frame: imagingFixture.frame,
          onChange: (state) => {
            if (!cancelled) setSyncState(state);
          },
        });
        syncRef.current = synchronizer;
        imageObserver = new ResizeObserver(() => {
          if (!cancelled) created.resize();
        });
        imageObserver.observe(element);
      } catch (error) {
        viewer?.dispose();
        if (!cancelled)
          setImageError(
            error instanceof Error
              ? error.message
              : 'Unable to initialize image/3D synchronization.',
          );
      }
    });

    return () => {
      cancelled = true;
      observer.disconnect();
      imageObserver?.disconnect();
      if (syncRef.current === synchronizer) syncRef.current = null;
      synchronizer?.dispose();
      viewer?.dispose();
      renderer.dispose();
    };
  }, []);

  const run = (command: (sync: ImagingPlaneSynchronizer) => Promise<void>) => {
    const sync = syncRef.current;
    if (!sync) return;
    void command(sync).then(
      () => {
        if (syncRef.current === sync) setImageError(null);
      },
      (error) => {
        if (syncRef.current === sync)
          setImageError(
            error instanceof Error
              ? error.message
              : 'Unable to synchronize planes.',
          );
      },
    );
  };
  const toggleClipping = () =>
    syncRef.current?.setClippingEnabled(!clippingEnabled);

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
            disabled={!syncState}
          >
            Clipping plane: {clippingEnabled ? 'On' : 'Off'}
          </button>
          <div className="viewer__plane-controls">
            <label htmlFor="patient-plane-k">
              3D axial plane · source voxel k
            </label>
            <input
              id="patient-plane-k"
              type="range"
              min={0}
              max={imagingFixture.frame.dimensions.k - 1}
              step={1}
              value={slice?.voxelK ?? 0}
              disabled={!syncState}
              onChange={(event) =>
                run((sync) => sync.setPlaneAtVoxelK(Number(event.target.value)))
              }
            />
            <output>
              {slice
                ? `k ${slice.voxelK} · z ${slice.plane.origin.value.z.toFixed(1)} mm`
                : '–'}
            </output>
          </div>
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
      <ImagingPanel
        elementRef={imageElementRef}
        slice={slice}
        imageError={imageError ?? syncState?.error ?? null}
        moveSlice={(index) => run((sync) => sync.setImageSlice(index))}
        scrollImage={(delta) => run((sync) => sync.scrollImage(delta))}
      />
    </main>
  );
}

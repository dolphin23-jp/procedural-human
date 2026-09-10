import { useEffect, useMemo, useRef, useState } from 'react';
import './as05-source-navigation.css';

interface SourceFrame {
  readonly index: number;
  readonly filename: string;
  readonly sourcePath: string;
  readonly sourceUrl: string;
  readonly listedByteSize: number;
  readonly navigationRegions: readonly string[];
  readonly availability: 'source-image' | 'provider-listed-zero-byte';
}

interface ProviderPartition {
  readonly name: string;
  readonly firstIndex: number;
  readonly lastIndex: number;
  readonly frameCount: number;
}

interface SourceNavigationIndex {
  readonly schema: 'ph-as05-source-navigation.v1';
  readonly schemaVersion: '1';
  readonly task: 'TASK-AS05';
  readonly generatedFrom: {
    readonly inventoryPath: string;
    readonly inventorySha256: string;
    readonly sourceArchiveId: string;
    readonly snapshotAt: string;
  };
  readonly coordinateSpace: 'source-image-stack';
  readonly claims: {
    readonly patientSpace: false;
    readonly registeredCT: false;
    readonly medicalValidation: false;
    readonly medicalMaster: false;
    readonly runtimeAsset: false;
    readonly segmentation: false;
  };
  readonly terms: {
    readonly attribution: string;
    readonly conditions: readonly string[];
    readonly url: string;
  };
  readonly counts: {
    readonly listedSourceCount: number;
    readonly usableImageCount: number;
    readonly unavailableSourceCount: number;
  };
  readonly providerPartitions: readonly ProviderPartition[];
  readonly knownGaps: readonly string[];
  readonly a05Reference: {
    readonly label: string;
    readonly firstIndex: number;
    readonly lastIndex: number;
    readonly firstFilename: string;
    readonly lastFilename: string;
  };
  readonly frames: readonly SourceFrame[];
}

const DATA_URL = `${import.meta.env.BASE_URL}as05-source-index.json`;

function clamp(index: number, count: number): number {
  return Math.max(0, Math.min(count - 1, index));
}

function parseFrameTarget(
  raw: string,
  frames: readonly SourceFrame[],
): number | null {
  const value = raw.trim();
  if (!value) return null;
  if (/^\d+$/.test(value)) {
    const index = Number(value);
    return Number.isSafeInteger(index) && index >= 0 && index < frames.length
      ? index
      : null;
  }
  const normalized = value.toLowerCase().endsWith('.png')
    ? value.toLowerCase()
    : `${value.toLowerCase()}.png`;
  const match = frames.find((frame) => frame.filename === normalized);
  return match?.index ?? null;
}

function byteLabel(bytes: number): string {
  if (bytes === 0) return '0 bytes';
  return `${(bytes / 1_000_000).toFixed(2)} MB listed`;
}

export function AS05SourceNavigator() {
  const [data, setData] = useState<SourceNavigationIndex | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [jumpValue, setJumpValue] = useState('0');
  const [fitMode, setFitMode] = useState<'fit' | 'native'>('fit');
  const initialTargetApplied = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void fetch(DATA_URL, { cache: 'no-cache' })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`navigation index HTTP ${response.status}`);
        }
        return (await response.json()) as SourceNavigationIndex;
      })
      .then((value) => {
        if (cancelled) return;
        if (
          value.schema !== 'ph-as05-source-navigation.v1' ||
          value.task !== 'TASK-AS05' ||
          value.coordinateSpace !== 'source-image-stack' ||
          value.frames.length !== value.counts.listedSourceCount
        ) {
          throw new Error('navigation index contract mismatch');
        }
        setData(value);
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(
            error instanceof Error ? error.message : 'Unable to load index.',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!data || initialTargetApplied.current) return;
    initialTargetApplied.current = true;
    const params = new URLSearchParams(window.location.search);
    const raw = params.get('frame');
    const requested = raw ? parseFrameTarget(raw, data.frames) : null;
    const next = requested ?? data.a05Reference.firstIndex;
    setFrameIndex(next);
    setJumpValue(String(next));
  }, [data]);

  const frame = data?.frames[frameIndex] ?? null;
  const available = frame?.availability === 'source-image';

  useEffect(() => {
    setImageError(null);
    if (!data || !frame) return;
    const params = new URLSearchParams(window.location.search);
    params.set('as05-source', '1');
    params.set('frame', frame.filename.replace(/\.png$/, ''));
    window.history.replaceState(null, '', `?${params.toString()}`);

    for (const index of [frameIndex - 1, frameIndex + 1]) {
      const adjacent = data.frames[index];
      if (adjacent?.availability === 'source-image') {
        const preload = new Image();
        preload.src = adjacent.sourceUrl;
      }
    }
  }, [data, frame, frameIndex]);

  useEffect(() => {
    if (!data) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLSelectElement ||
        event.target instanceof HTMLTextAreaElement
      ) {
        return;
      }
      const delta =
        event.key === 'ArrowLeft'
          ? -1
          : event.key === 'ArrowRight'
            ? 1
            : event.key === 'PageUp'
              ? -10
              : event.key === 'PageDown'
                ? 10
                : 0;
      if (!delta) return;
      event.preventDefault();
      setFrameIndex((current) => clamp(current + delta, data.frames.length));
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [data]);

  const sourceNotice = useMemo(() => {
    if (!frame) return '';
    return frame.navigationRegions.length
      ? frame.navigationRegions.join(', ')
      : 'unclassified provider partition';
  }, [frame]);

  const move = (delta: number) => {
    if (!data) return;
    setFrameIndex((current) => clamp(current + delta, data.frames.length));
  };

  const jump = () => {
    if (!data) return;
    const target = parseFrameTarget(jumpValue, data.frames);
    if (target === null) {
      setLoadError('Frame jump must be a valid global index or avf####x filename.');
      return;
    }
    setLoadError(null);
    setFrameIndex(target);
  };

  if (!data) {
    return (
      <main className="as05-source as05-source__unavailable">
        <p className="as05-source__eyebrow">TASK-AS05</p>
        <h1>Whole-body source navigator</h1>
        <p>
          {loadError
            ? `Navigation data unavailable: ${loadError}`
            : 'Loading indexed source navigation data…'}
        </p>
        <a href={import.meta.env.BASE_URL}>Back to development preview</a>
      </main>
    );
  }

  return (
    <main className="as05-source">
      <header className="as05-source__header">
        <div>
          <p className="as05-source__eyebrow">TASK-AS05 · Authoring source view</p>
          <h1>Visible Human Female whole-body source navigator</h1>
          <p className="as05-source__subhead">
            Same-subject source/reference inspection only. No overlay is active.
            Viewing a frame does not establish segmentation, anatomical identity,
            validation, Patient Space, or CT registration.
          </p>
        </div>
        <div className="as05-source__header-actions">
          <a href="?a06-review=1">A06 review</a>
          <a href={import.meta.env.BASE_URL}>3D preview</a>
        </div>
      </header>

      <section className="as05-source__legal" aria-label="Source terms and claims">
        <strong>{data.terms.attribution}</strong>
        <span>
          Snapshot {data.generatedFrom.snapshotAt} · source-image-stack coordinates
          only
        </span>
        <span>
          {data.counts.usableImageCount.toLocaleString()} usable PNGs /{' '}
          {data.counts.listedSourceCount.toLocaleString()} listed source identities
        </span>
      </section>

      <section className="as05-source__jump" aria-label="Source navigation controls">
        <label>
          Jump to global index or filename
          <div className="as05-source__jump-row">
            <input
              value={jumpValue}
              onChange={(event) => setJumpValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') jump();
              }}
              placeholder="1698 or avf1567a"
            />
            <button type="button" onClick={jump}>
              Go
            </button>
          </div>
        </label>
        <label>
          Provider partition
          <select
            value=""
            onChange={(event) => {
              const target = Number(event.target.value);
              if (Number.isFinite(target)) {
                setFrameIndex(target);
                setJumpValue(String(target));
              }
            }}
          >
            <option value="" disabled>
              Jump to partition…
            </option>
            {data.providerPartitions.map((partition) => (
              <option key={partition.name} value={partition.firstIndex}>
                {partition.name} · {partition.frameCount} indexed identities
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="as05-source__a05-jump"
          onClick={() => {
            setFrameIndex(data.a05Reference.firstIndex);
            setJumpValue(String(data.a05Reference.firstIndex));
          }}
        >
          A05 distal forearm start
        </button>
        <button
          type="button"
          className="as05-source__fit"
          aria-pressed={fitMode === 'native'}
          onClick={() =>
            setFitMode((current) => (current === 'fit' ? 'native' : 'fit'))
          }
        >
          {fitMode === 'fit' ? '1:1 pixels' : 'Fit image'}
        </button>
        {loadError && <p className="as05-source__error">{loadError}</p>}
      </section>

      <section className="as05-source__navigation" aria-label="Sequential navigation">
        <button type="button" onClick={() => move(-100)} disabled={frameIndex === 0}>
          −100
        </button>
        <button type="button" onClick={() => move(-10)} disabled={frameIndex === 0}>
          −10
        </button>
        <button type="button" onClick={() => move(-1)} disabled={frameIndex === 0}>
          Previous
        </button>
        <input
          aria-label="Global source frame"
          type="range"
          min={0}
          max={data.frames.length - 1}
          step={1}
          value={frameIndex}
          onChange={(event) => {
            const next = Number(event.target.value);
            setFrameIndex(next);
            setJumpValue(String(next));
          }}
        />
        <output>
          {frameIndex.toLocaleString()} / {(data.frames.length - 1).toLocaleString()}
        </output>
        <button
          type="button"
          onClick={() => move(1)}
          disabled={frameIndex === data.frames.length - 1}
        >
          Next
        </button>
        <button
          type="button"
          onClick={() => move(10)}
          disabled={frameIndex === data.frames.length - 1}
        >
          +10
        </button>
        <button
          type="button"
          onClick={() => move(100)}
          disabled={frameIndex === data.frames.length - 1}
        >
          +100
        </button>
      </section>

      {frame && (
        <section className="as05-source__workspace">
          <article className="as05-source__image-panel">
            <header>
              <div>
                <p className="as05-source__eyebrow">Global index {frame.index}</p>
                <h2>{frame.filename}</h2>
              </div>
              <span
                className={
                  available
                    ? 'as05-source__availability'
                    : 'as05-source__availability as05-source__availability--gap'
                }
              >
                {available ? 'Recorded source image' : 'Provider-listed 0-byte gap'}
              </span>
            </header>
            <div
              className="as05-source__image-scroll"
              data-fit-mode={fitMode}
              aria-label={`Source image ${frame.filename}`}
            >
              {available ? (
                <img
                  key={frame.sourceUrl}
                  src={frame.sourceUrl}
                  alt={`Visible Human Female source frame ${frame.filename}`}
                  onError={() =>
                    setImageError(
                      'The recorded provider URL did not return a displayable image. No alternate source is substituted automatically.',
                    )
                  }
                  onLoad={() => setImageError(null)}
                  draggable={false}
                />
              ) : (
                <div className="as05-source__gap">
                  <strong>No image bytes exist in the recorded provider listing.</strong>
                  <p>
                    This source identity is retained for continuity accounting but
                    is unavailable for visual interpretation.
                  </p>
                </div>
              )}
            </div>
            {imageError && <p className="as05-source__error">{imageError}</p>}
          </article>

          <aside className="as05-source__metadata" aria-label="Source provenance">
            <p className="as05-source__eyebrow">Source identity / provenance</p>
            <dl>
              <dt>Global index</dt>
              <dd>{frame.index}</dd>
              <dt>Filename</dt>
              <dd>{frame.filename}</dd>
              <dt>Recorded source path</dt>
              <dd>{frame.sourcePath}</dd>
              <dt>Provider partition metadata</dt>
              <dd>{sourceNotice}</dd>
              <dt>Listed byte size</dt>
              <dd>{byteLabel(frame.listedByteSize)}</dd>
              <dt>Coordinate space</dt>
              <dd>{data.coordinateSpace}</dd>
              <dt>Inventory SHA-256</dt>
              <dd>{data.generatedFrom.inventorySha256}</dd>
            </dl>
            {available && (
              <a
                className="as05-source__source-link"
                href={frame.sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                Open recorded provider source
              </a>
            )}
            <div className="as05-source__claim-box">
              <strong>Viewing claims</strong>
              <p>
                Segmentation: false · medical validation: false · Patient Space:
                false · CT registration: false · Medical Master: false
              </p>
            </div>
            <details>
              <summary>Known source gaps</summary>
              <ul>
                {data.knownGaps.map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
              </ul>
            </details>
            <details>
              <summary>Keyboard navigation</summary>
              <p>← / → one frame · Page Up / Page Down ten frames.</p>
            </details>
          </aside>
        </section>
      )}

      <footer className="as05-source__footer">
        <span>{data.generatedFrom.sourceArchiveId}</span>
        <span>
          Compact navigator is derived from {data.generatedFrom.inventoryPath}; it
          is not a second source archive.
        </span>
      </footer>
    </main>
  );
}

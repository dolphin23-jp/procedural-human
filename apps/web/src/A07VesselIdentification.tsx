import {
  useEffect,
  useMemo,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react';
import './a07-vessel-identification.css';

type VesselTargetKey = 'radial_artery' | 'superficial_target_vein';
type DecisionKind = 'identified' | 'uncertain' | 'not-identifiable';
type SuperficialIdentity = 'unresolved' | 'cephalic' | 'basilic';

interface ReviewStructure {
  readonly draftLabel: string;
  readonly maskPathPrefix: string;
}

interface ReviewManifest {
  readonly schema: 'ph-a06-ipad-review-data.v1';
  readonly schemaVersion: '1';
  readonly task: 'TASK-A06';
  readonly assetRevision: string;
  readonly source: {
    readonly dataset: string;
    readonly frameCount: 451;
    readonly firstSourceFilename: 'avf1567a.png';
    readonly lastSourceFilename: 'avf1717a.png';
    readonly cropDimensionsPixels: {
      readonly width: 550;
      readonly height: 750;
    };
    readonly cropFilenameShaAggregate: string;
    readonly imagePathPrefix: string;
  };
  readonly structures: readonly ReviewStructure[];
  readonly distribution: {
    readonly attribution: string;
    readonly noEndorsement: string;
    readonly currencyNotice: string;
  };
}

interface SourcePoint {
  readonly x: number;
  readonly y: number;
}

interface IdentificationDecision {
  readonly decision: DecisionKind;
  readonly point?: SourcePoint;
  readonly note?: string;
}

interface SavedSession {
  readonly reviewerReference: string;
  readonly startedAt: string;
  readonly superficialIdentity: SuperficialIdentity;
  readonly decisions: Record<string, IdentificationDecision>;
  readonly overlays: {
    readonly radius: boolean;
    readonly ulna: boolean;
    readonly ulnar_artery: boolean;
  };
}

const REVIEW_DATA_ROOT = `${import.meta.env.BASE_URL}a06-review-data/`;
const ANCHOR_FIRST = 237;
const ANCHOR_LAST = 342;
const ANCHOR_STRIDE = 3;
const ANCHOR_FRAMES = Array.from(
  { length: (ANCHOR_LAST - ANCHOR_FIRST) / ANCHOR_STRIDE + 1 },
  (_, index) => ANCHOR_FIRST + index * ANCHOR_STRIDE,
);

const TARGETS: readonly {
  readonly key: VesselTargetKey;
  readonly title: string;
  readonly shortTitle: string;
  readonly instruction: string;
}[] = [
  {
    key: 'radial_artery',
    title: 'Radial artery',
    shortTitle: 'Radial artery',
    instruction:
      'Mark a point only when you can directly identify the radial artery in the source slice. Radius, ulna, and the already reviewed ulnar artery are orientation context only. Do not place a point from expected anatomy alone.',
  },
  {
    key: 'superficial_target_vein',
    title: 'Superficial target vein',
    shortTitle: 'Superficial vein',
    instruction:
      'Mark one source-visible superficial venous structure in the subcutaneous tissue. Keep identity unresolved unless continuity and side support a cephalic- or basilic-vein candidate. Do not select a target merely because it would be useful for a procedure.',
  },
];

function boundedFrameNames(): readonly string[] {
  const names: string[] = [];
  for (let position = 1567; position < 1717; position += 1) {
    for (const suffix of ['a', 'b', 'c'] as const) {
      names.push(`avf${String(position).padStart(4, '0')}${suffix}.png`);
    }
  }
  names.push('avf1717a.png');
  return names;
}

const ALL_FRAME_NAMES = boundedFrameNames();

function frameFilename(globalFrameIndex: number): string {
  const filename = ALL_FRAME_NAMES[globalFrameIndex];
  if (!filename) {
    throw new Error(`No source filename for global frame ${globalFrameIndex}.`);
  }
  return filename;
}

function imageStem(filename: string): string {
  return filename.replace(/\.png$/, '');
}

function decisionKey(
  target: VesselTargetKey,
  globalFrameIndex: number,
): string {
  return `${target}:${globalFrameIndex}`;
}

function loadSavedSession(assetRevision: string): SavedSession | null {
  const raw = window.localStorage.getItem(
    `ph-a07-source-identification:${assetRevision}`,
  );
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<SavedSession>;
    if (
      typeof parsed.reviewerReference !== 'string' ||
      typeof parsed.startedAt !== 'string' ||
      !['unresolved', 'cephalic', 'basilic'].includes(
        parsed.superficialIdentity ?? '',
      ) ||
      typeof parsed.decisions !== 'object' ||
      parsed.decisions === null ||
      typeof parsed.overlays !== 'object' ||
      parsed.overlays === null
    ) {
      return null;
    }
    return parsed as SavedSession;
  } catch {
    return null;
  }
}

function countTargetDecisions(
  target: VesselTargetKey,
  decisions: Record<string, IdentificationDecision>,
) {
  let decided = 0;
  let identified = 0;
  let uncertain = 0;
  let notIdentifiable = 0;

  for (const frame of ANCHOR_FRAMES) {
    const row = decisions[decisionKey(target, frame)];
    if (!row) continue;
    decided += 1;
    if (row.decision === 'identified') identified += 1;
    else if (row.decision === 'uncertain') uncertain += 1;
    else notIdentifiable += 1;
  }

  return {
    decided,
    identified,
    uncertain,
    notIdentifiable,
    complete: decided === ANCHOR_FRAMES.length,
  };
}

export function A07VesselIdentification() {
  const [manifest, setManifest] = useState<ReviewManifest | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [targetKey, setTargetKey] =
    useState<VesselTargetKey>('radial_artery');
  const [anchorIndex, setAnchorIndex] = useState(0);
  const [reviewerReference, setReviewerReference] = useState('');
  const [startedAt, setStartedAt] = useState(() => new Date().toISOString());
  const [superficialIdentity, setSuperficialIdentity] =
    useState<SuperficialIdentity>('unresolved');
  const [decisions, setDecisions] = useState<
    Record<string, IdentificationDecision>
  >({});
  const [draftPoint, setDraftPoint] = useState<SourcePoint | null>(null);
  const [noteDraft, setNoteDraft] = useState('');
  const [exportError, setExportError] = useState<string | null>(null);
  const [overlays, setOverlays] = useState({
    radius: true,
    ulna: true,
    ulnar_artery: true,
  });

  useEffect(() => {
    let cancelled = false;
    void fetch(`${REVIEW_DATA_ROOT}manifest.json`, { cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(
            `Source review data unavailable (HTTP ${response.status}).`,
          );
        }
        return (await response.json()) as ReviewManifest;
      })
      .then((loaded) => {
        if (cancelled) return;
        const labels = new Set(
          loaded.structures.map((structure) => structure.draftLabel),
        );
        if (
          loaded.schema !== 'ph-a06-ipad-review-data.v1' ||
          loaded.source.frameCount !== 451 ||
          !['radius', 'ulna', 'ulnar_artery'].every((label) =>
            labels.has(label),
          )
        ) {
          throw new Error(
            'Unexpected or incomplete TASK-A06 source review manifest.',
          );
        }
        setManifest(loaded);
        const saved = loadSavedSession(loaded.assetRevision);
        if (saved) {
          setReviewerReference(saved.reviewerReference);
          setStartedAt(saved.startedAt);
          setSuperficialIdentity(saved.superficialIdentity);
          setDecisions(saved.decisions);
          setOverlays(saved.overlays);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(
            error instanceof Error
              ? error.message
              : 'Unable to load source review data.',
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!manifest) return;
    const saved: SavedSession = {
      reviewerReference,
      startedAt,
      superficialIdentity,
      decisions,
      overlays,
    };
    window.localStorage.setItem(
      `ph-a07-source-identification:${manifest.assetRevision}`,
      JSON.stringify(saved),
    );
  }, [
    manifest,
    reviewerReference,
    startedAt,
    superficialIdentity,
    decisions,
    overlays,
  ]);

  const globalFrameIndex = ANCHOR_FRAMES[anchorIndex] ?? ANCHOR_FIRST;
  const filename = frameFilename(globalFrameIndex);
  const target =
    TARGETS.find((candidate) => candidate.key === targetKey) ?? TARGETS[0];
  const savedDecision = decisions[decisionKey(targetKey, globalFrameIndex)];

  useEffect(() => {
    const row = decisions[decisionKey(targetKey, globalFrameIndex)];
    setDraftPoint(row?.decision === 'identified' ? row.point ?? null : null);
    setNoteDraft(row?.note ?? '');
  }, [decisions, targetKey, globalFrameIndex]);

  const structurePaths = useMemo(() => {
    const map = new Map<string, string>();
    for (const structure of manifest?.structures ?? []) {
      map.set(structure.draftLabel, structure.maskPathPrefix);
    }
    return map;
  }, [manifest]);

  const progress = useMemo(
    () => ({
      radial: countTargetDecisions('radial_artery', decisions),
      superficial: countTargetDecisions('superficial_target_vein', decisions),
    }),
    [decisions],
  );

  const advance = () => {
    setAnchorIndex((current) =>
      Math.min(ANCHOR_FRAMES.length - 1, current + 1),
    );
  };

  const saveDecision = (decision: DecisionKind) => {
    if (decision === 'identified' && !draftPoint) return;

    const note = noteDraft.trim().slice(0, 2000);
    const row: IdentificationDecision =
      decision === 'identified'
        ? {
            decision,
            point: draftPoint ?? undefined,
            ...(note ? { note } : {}),
          }
        : {
            decision,
            ...(note ? { note } : {}),
          };

    setDecisions((current) => ({
      ...current,
      [decisionKey(targetKey, globalFrameIndex)]: row,
    }));
    advance();
  };

  const clearDecision = () => {
    setDecisions((current) => {
      const next = { ...current };
      delete next[decisionKey(targetKey, globalFrameIndex)];
      return next;
    });
    setDraftPoint(null);
    setNoteDraft('');
  };

  const placePoint = (event: ReactPointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const x = Math.max(
      0,
      Math.min(
        550,
        ((event.clientX - rect.left) / rect.width) * 550,
      ),
    );
    const y = Math.max(
      0,
      Math.min(
        750,
        ((event.clientY - rect.top) / rect.height) * 750,
      ),
    );
    setDraftPoint({ x, y });
  };

  const exportSession = () => {
    if (!manifest) return;
    const reviewer = reviewerReference.trim();
    if (!reviewer) {
      setExportError('Enter a reviewer reference before exporting.');
      return;
    }

    const buildTarget = (key: VesselTargetKey) => {
      const counts = countTargetDecisions(key, decisions);
      const decisionRows = ANCHOR_FRAMES.flatMap((frame) => {
        const row = decisions[decisionKey(key, frame)];
        if (!row) return [];
        const base = {
          globalFrameIndex: frame,
          sourceFilename: frameFilename(frame),
          decision: row.decision,
          ...(row.note ? { note: row.note } : {}),
        };
        return [
          row.decision === 'identified' && row.point
            ? {
                ...base,
                xSourcePixels: row.point.x,
                ySourcePixels: row.point.y,
              }
            : base,
        ];
      });

      if (key === 'radial_artery') {
        return {
          targetKey: key,
          anatomicalIdentity: 'structure.radial_artery.left',
          identityDisposition: 'fixed-by-task',
          anchorCount: ANCHOR_FRAMES.length,
          decidedCount: counts.decided,
          identifiedCount: counts.identified,
          uncertainCount: counts.uncertain,
          notIdentifiableCount: counts.notIdentifiable,
          complete: counts.complete,
          decisions: decisionRows,
        };
      }

      const identity =
        superficialIdentity === 'cephalic'
          ? 'structure.cephalic_vein.left'
          : superficialIdentity === 'basilic'
            ? 'structure.basilic_vein.left'
            : null;
      return {
        targetKey: key,
        anatomicalIdentity: identity,
        identityDisposition:
          identity === null ? 'unresolved' : 'human-source-candidate',
        anchorCount: ANCHOR_FRAMES.length,
        decidedCount: counts.decided,
        identifiedCount: counts.identified,
        uncertainCount: counts.uncertain,
        notIdentifiableCount: counts.notIdentifiable,
        complete: counts.complete,
        decisions: decisionRows,
      };
    };

    const targets = [
      buildTarget('radial_artery'),
      buildTarget('superficial_target_vein'),
    ];
    const complete = targets.every((row) => row.complete);
    const allIdentified =
      complete &&
      targets.every(
        (row) =>
          row.identifiedCount === ANCHOR_FRAMES.length &&
          row.uncertainCount === 0 &&
          row.notIdentifiableCount === 0,
      );

    const payload = {
      schema: 'ph-a07-source-vessel-identification-session.v1',
      schemaVersion: '1',
      task: 'TASK-A07',
      assetRevision: manifest.assetRevision,
      reviewerReference: reviewer,
      reviewTool: 'Procedural Human A07 iPad Source Vessel Identification',
      reviewToolVersion: '1',
      startedAt,
      exportedAt: new Date().toISOString(),
      sessionStatus: complete
        ? allIdentified
          ? 'complete-all-identified'
          : 'complete-with-gaps'
        : 'partial',
      coordinateSpace: {
        kind: 'source-image-stack',
        patientSpaceClaim: false,
        ctRegistrationEstablished: false,
      },
      source: {
        dataset: manifest.source.dataset,
        frameCount: manifest.source.frameCount,
        firstSourceFilename: manifest.source.firstSourceFilename,
        lastSourceFilename: manifest.source.lastSourceFilename,
        cropWidthPixels: manifest.source.cropDimensionsPixels.width,
        cropHeightPixels: manifest.source.cropDimensionsPixels.height,
        cropFilenameShaAggregate: manifest.source.cropFilenameShaAggregate,
      },
      anchorPlan: {
        firstGlobalFrameIndex: ANCHOR_FIRST,
        lastGlobalFrameIndex: ANCHOR_LAST,
        strideFrames: ANCHOR_STRIDE,
        anchorCount: ANCHOR_FRAMES.length,
      },
      evidenceStrategy: {
        algorithmicVesselSuggestionShown: false,
        contextOverlays: ['radius', 'ulna', 'ulnar_artery'],
        interpretationRule:
          'mark-only-source-visible-vessel-do-not-place-by-anatomical-expectation-alone',
      },
      targets,
      claims: {
        humanSourceIdentificationInputRecorded: true,
        sourceImageSupportEstablished: false,
        anatomicallyReviewed: false,
        procedureSpecificReview: false,
        medicalValidation: false,
        patientSpaceGeometry: false,
        superficialTargetVeinSelected: false,
        automaticPromotionAllowed: false,
      },
    };

    const blob = new Blob([JSON.stringify(payload, null, 2) + '\n'], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    const date = new Date().toISOString().slice(0, 10);
    anchor.href = url;
    anchor.download = `a07-source-vessel-identification-${date}.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setExportError(null);
  };

  const resetSession = () => {
    if (!manifest) return;
    if (
      !window.confirm(
        'Clear all locally saved TASK-A07 source-identification decisions?',
      )
    ) {
      return;
    }
    window.localStorage.removeItem(
      `ph-a07-source-identification:${manifest.assetRevision}`,
    );
    setReviewerReference('');
    setStartedAt(new Date().toISOString());
    setSuperficialIdentity('unresolved');
    setDecisions({});
    setDraftPoint(null);
    setNoteDraft('');
    setAnchorIndex(0);
    setTargetKey('radial_artery');
    setOverlays({ radius: true, ulna: true, ulnar_artery: true });
    setExportError(null);
  };

  if (loadError) {
    return (
      <main className="a07-id">
        <section className="a07-id__panel a07-id__unavailable">
          <p className="a07-id__eyebrow">TASK-A07 · Source identification</p>
          <h1>Source data unavailable</h1>
          <p>{loadError}</p>
          <a href={import.meta.env.BASE_URL}>Return to the 3D preview</a>
        </section>
      </main>
    );
  }

  if (!manifest) {
    return (
      <main className="a07-id">
        <section className="a07-id__panel a07-id__unavailable">
          <p>Loading source-identification data…</p>
        </section>
      </main>
    );
  }

  const radialProgress = progress.radial;
  const superficialProgress = progress.superficial;
  const maskImage = (
    label: 'radius' | 'ulna' | 'ulnar_artery',
    enabled: boolean,
  ) => {
    const prefix = structurePaths.get(label);
    if (!prefix || !enabled) return null;
    return (
      <img
        className={`a07-id__mask a07-id__mask--${label}`}
        src={`${REVIEW_DATA_ROOT}${prefix}${filename}`}
        alt=""
        draggable={false}
      />
    );
  };

  return (
    <main className="a07-id">
      <header className="a07-id__header">
        <div>
          <p className="a07-id__eyebrow">
            TASK-A07 · Independent human source identification
          </p>
          <h1>Distal forearm vessel anchors</h1>
          <p className="a07-id__subhead">
            Directly mark source-visible vessel centers on 36 sparse anchor
            slices. No failed algorithmic or atlas vessel suggestion is shown.
            Context overlays are orientation aids only.
          </p>
        </div>
        <a className="a07-id__back" href={import.meta.env.BASE_URL}>
          3D preview
        </a>
      </header>

      <section className="a07-id__legal">
        <strong>{manifest.distribution.attribution}</strong>
        <span>{manifest.distribution.noEndorsement}</span>
        <span>{manifest.distribution.currencyNotice}</span>
      </section>

      <section className="a07-id__panel a07-id__safety">
        <strong>Evidence rule</strong>
        <p>
          Mark only a vessel that is directly visible in the cryosection.
          Choosing “uncertain” or “not identifiable” is preferable to placing a
          point from anatomical expectation. This session is human source
          identification input only; it is not anatomical review, procedure
          validation, Patient Space geometry, or Medical Master approval.
        </p>
      </section>

      <section className="a07-id__panel a07-id__toolbar">
        <label>
          Reviewer reference
          <input
            value={reviewerReference}
            onChange={(event) => setReviewerReference(event.target.value)}
            placeholder="e.g. initials or local reviewer ID"
            autoComplete="off"
          />
        </label>
        <div className="a07-id__toolbar-actions">
          <button type="button" onClick={exportSession}>
            Export identification JSON
          </button>
          <button
            type="button"
            className="a07-id__secondary"
            onClick={resetSession}
          >
            Reset local session
          </button>
        </div>
        {exportError && <p className="a07-id__error">{exportError}</p>}
      </section>

      <nav className="a07-id__targets" aria-label="Vessel targets">
        <button
          type="button"
          aria-pressed={targetKey === 'radial_artery'}
          onClick={() => {
            setTargetKey('radial_artery');
            setAnchorIndex(0);
          }}
        >
          <strong>Radial artery</strong>
          <span>
            {radialProgress.decided}/{ANCHOR_FRAMES.length} decided ·{' '}
            {radialProgress.identified} identified
          </span>
        </button>
        <button
          type="button"
          aria-pressed={targetKey === 'superficial_target_vein'}
          onClick={() => {
            setTargetKey('superficial_target_vein');
            setAnchorIndex(0);
          }}
        >
          <strong>Superficial target vein</strong>
          <span>
            {superficialProgress.decided}/{ANCHOR_FRAMES.length} decided ·{' '}
            {superficialProgress.identified} identified
          </span>
        </button>
      </nav>

      <section className="a07-id__panel a07-id__task">
        <div>
          <p className="a07-id__eyebrow">{target.shortTitle}</p>
          <h2>{target.title}</h2>
          <p>{target.instruction}</p>
        </div>
        {targetKey === 'superficial_target_vein' && (
          <label className="a07-id__identity">
            Identity candidate from source continuity
            <select
              value={superficialIdentity}
              onChange={(event) =>
                setSuperficialIdentity(
                  event.target.value as SuperficialIdentity,
                )
              }
            >
              <option value="unresolved">Unresolved</option>
              <option value="cephalic">Cephalic vein candidate</option>
              <option value="basilic">Basilic vein candidate</option>
            </select>
            <small>
              Leave unresolved unless the source sequence itself supports the
              name. This does not select a procedural target.
            </small>
          </label>
        )}
      </section>

      <section className="a07-id__panel a07-id__overlay-controls">
        <span>Orientation overlays</span>
        {(
          [
            ['radius', 'Radius'],
            ['ulna', 'Ulna'],
            ['ulnar_artery', 'Reviewed ulnar artery'],
          ] as const
        ).map(([key, label]) => (
          <label key={key}>
            <input
              type="checkbox"
              checked={overlays[key]}
              onChange={(event) =>
                setOverlays((current) => ({
                  ...current,
                  [key]: event.target.checked,
                }))
              }
            />
            {label}
          </label>
        ))}
      </section>

      <section className="a07-id__frame-layout">
        <div className="a07-id__panel a07-id__viewer-panel">
          <div className="a07-id__frame-heading">
            <div>
              <p className="a07-id__eyebrow">
                Anchor {anchorIndex + 1} / {ANCHOR_FRAMES.length}
              </p>
              <h2>{filename}</h2>
              <span>global frame {globalFrameIndex}</span>
            </div>
            <div className="a07-id__frame-state">
              {savedDecision?.decision ?? 'unreviewed'}
            </div>
          </div>

          <div
            className="a07-id__viewer"
            onPointerDown={placePoint}
            role="application"
            aria-label={`Source slice ${filename}; tap to place vessel center`}
          >
            <img
              className="a07-id__source"
              src={`${REVIEW_DATA_ROOT}${manifest.source.imagePathPrefix}${imageStem(filename)}.webp`}
              alt={`Visible Human Female source slice ${filename}`}
              draggable={false}
            />
            {maskImage('radius', overlays.radius)}
            {maskImage('ulna', overlays.ulna)}
            {maskImage('ulnar_artery', overlays.ulnar_artery)}
            {draftPoint && (
              <span
                className="a07-id__crosshair"
                style={{
                  left: `${(draftPoint.x / 550) * 100}%`,
                  top: `${(draftPoint.y / 750) * 100}%`,
                }}
                aria-hidden="true"
              />
            )}
          </div>

          <p className="a07-id__coordinate">
            {draftPoint
              ? `Draft point: x=${draftPoint.x.toFixed(1)}, y=${draftPoint.y.toFixed(1)} source pixels`
              : 'Tap the source image to place a draft center point.'}
          </p>
        </div>

        <aside className="a07-id__panel a07-id__decision-panel">
          <div className="a07-id__nav">
            <button
              type="button"
              disabled={anchorIndex === 0}
              onClick={() =>
                setAnchorIndex((current) => Math.max(0, current - 1))
              }
            >
              Previous
            </button>
            <button
              type="button"
              disabled={anchorIndex === ANCHOR_FRAMES.length - 1}
              onClick={() =>
                setAnchorIndex((current) =>
                  Math.min(ANCHOR_FRAMES.length - 1, current + 1),
                )
              }
            >
              Next
            </button>
          </div>

          <label className="a07-id__note">
            Optional note
            <textarea
              value={noteDraft}
              maxLength={2000}
              onChange={(event) => setNoteDraft(event.target.value)}
              placeholder="Why the vessel is uncertain, image artifact, continuity observation, etc."
            />
          </label>

          <div className="a07-id__decision-actions">
            <button
              type="button"
              className="a07-id__identified"
              disabled={!draftPoint}
              onClick={() => saveDecision('identified')}
            >
              Save point & next
            </button>
            <button
              type="button"
              onClick={() => saveDecision('uncertain')}
            >
              Uncertain & next
            </button>
            <button
              type="button"
              onClick={() => saveDecision('not-identifiable')}
            >
              Not identifiable & next
            </button>
            <button
              type="button"
              className="a07-id__secondary"
              onClick={clearDecision}
            >
              Clear this decision
            </button>
          </div>

          <div className="a07-id__counts">
            <strong>Current target</strong>
            <span>
              Decided:{' '}
              {targetKey === 'radial_artery'
                ? radialProgress.decided
                : superficialProgress.decided}
              /{ANCHOR_FRAMES.length}
            </span>
            <span>
              Identified:{' '}
              {targetKey === 'radial_artery'
                ? radialProgress.identified
                : superficialProgress.identified}
            </span>
            <span>
              Uncertain:{' '}
              {targetKey === 'radial_artery'
                ? radialProgress.uncertain
                : superficialProgress.uncertain}
            </span>
            <span>
              Not identifiable:{' '}
              {targetKey === 'radial_artery'
                ? radialProgress.notIdentifiable
                : superficialProgress.notIdentifiable}
            </span>
          </div>
        </aside>
      </section>

      <footer className="a07-id__footer">
        <span>
          Review asset revision: {manifest.assetRevision}
        </span>
        <span>
          Anchor range: global {ANCHOR_FIRST}–{ANCHOR_LAST}, stride{' '}
          {ANCHOR_STRIDE} frames
        </span>
      </footer>
    </main>
  );
}

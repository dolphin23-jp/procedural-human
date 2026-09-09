import { useEffect, useMemo, useState } from 'react';
import './a06-review.css';

type ReviewDecisionKind = 'accepted' | 'flagged';

interface ReviewDecision {
  readonly decision: ReviewDecisionKind;
  readonly note?: string;
}

interface ReviewStructure {
  readonly draftLabel: string;
  readonly displayName: string;
  readonly sourceClass: string;
  readonly supportStatus: string;
  readonly supportedFrameCount: number;
  readonly firstSourceFilename: string;
  readonly lastSourceFilename: string;
  readonly maskPathPrefix: string;
}

interface ReviewManifest {
  readonly schema: 'ph-a06-ipad-review-data.v1';
  readonly schemaVersion: '1';
  readonly task: 'TASK-A06';
  readonly assetRevision: string;
  readonly coordinateSpace: {
    readonly kind: 'source-image-stack';
    readonly patientSpaceClaim: false;
    readonly ctRegistrationEstablished: false;
  };
  readonly source: {
    readonly dataset: string;
    readonly sourceClass: string;
    readonly frameCount: 451;
    readonly firstSourceFilename: 'avf1567a.png';
    readonly lastSourceFilename: 'avf1717a.png';
    readonly cropDimensionsPixels: {
      readonly width: 550;
      readonly height: 750;
    };
    readonly cropFilenameShaAggregate: string;
    readonly imageFormat: 'webp';
    readonly imagePathPrefix: string;
  };
  readonly structures: readonly ReviewStructure[];
  readonly distribution: {
    readonly sourceSnapshotRecordedAt: string;
    readonly attribution: string;
    readonly noEndorsement: string;
    readonly currencyNotice: string;
    readonly reviewPurposeOnly: true;
  };
  readonly claims: {
    readonly humanReviewRecorded: false;
    readonly anatomicallyReviewed: false;
    readonly medicalValidation: false;
    readonly patientSpaceGeometry: false;
    readonly medicalMaster: false;
    readonly runtimeAsset: false;
    readonly automaticPromotionAllowed: false;
  };
}

interface SavedReview {
  readonly reviewerReference: string;
  readonly startedAt: string;
  readonly decisions: Record<string, ReviewDecision>;
}

const PAGE_SIZE = 18;
const REVIEW_DATA_ROOT = `${import.meta.env.BASE_URL}a06-review-data/`;

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
const FRAME_INDEX = new Map(
  ALL_FRAME_NAMES.map((filename, index) => [filename, index] as const),
);

function supportedFrames(structure: ReviewStructure): readonly string[] {
  const start = FRAME_INDEX.get(structure.firstSourceFilename);
  const end = FRAME_INDEX.get(structure.lastSourceFilename);
  if (start === undefined || end === undefined || start > end) return [];
  const frames = ALL_FRAME_NAMES.slice(start, end + 1);
  return frames.length === structure.supportedFrameCount ? frames : [];
}

function decisionKey(label: string, filename: string): string {
  return `${label}/${filename}`;
}

function imageStem(filename: string): string {
  return filename.replace(/\.png$/, '');
}

function loadSavedReview(assetRevision: string): SavedReview | null {
  const raw = window.localStorage.getItem(`ph-a06-review:${assetRevision}`);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<SavedReview>;
    if (
      typeof parsed.reviewerReference !== 'string' ||
      typeof parsed.startedAt !== 'string' ||
      typeof parsed.decisions !== 'object' ||
      parsed.decisions === null
    ) {
      return null;
    }
    return {
      reviewerReference: parsed.reviewerReference,
      startedAt: parsed.startedAt,
      decisions: parsed.decisions as Record<string, ReviewDecision>,
    };
  } catch {
    return null;
  }
}

function ReviewImage({
  filename,
  structure,
  opacity,
  onOpen,
}: {
  readonly filename: string;
  readonly structure: ReviewStructure;
  readonly opacity: number;
  readonly onOpen: () => void;
}) {
  const stem = imageStem(filename);
  return (
    <button
      type="button"
      className="a06-review__image-button"
      onClick={onOpen}
      aria-label={`Open ${filename} for detailed review`}
    >
      <span className="a06-review__image-stack">
        <img
          src={`${REVIEW_DATA_ROOT}${structure ? 'source/' : ''}${stem}.webp`}
          alt=""
          loading="lazy"
        />
        <img
          className="a06-review__mask"
          src={`${REVIEW_DATA_ROOT}${structure.maskPathPrefix}${filename}`}
          alt=""
          loading="lazy"
          style={{ opacity }}
        />
      </span>
    </button>
  );
}

export function A06Review() {
  const [manifest, setManifest] = useState<ReviewManifest | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [structureIndex, setStructureIndex] = useState(0);
  const [pageIndex, setPageIndex] = useState(0);
  const [maskOpacity, setMaskOpacity] = useState(0.45);
  const [reviewerReference, setReviewerReference] = useState('');
  const [startedAt, setStartedAt] = useState(() => new Date().toISOString());
  const [decisions, setDecisions] = useState<Record<string, ReviewDecision>>({});
  const [openFilename, setOpenFilename] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetch(`${REVIEW_DATA_ROOT}manifest.json`, { cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(
            `Review data unavailable (HTTP ${response.status}). The normal 3D preview remains usable.`,
          );
        }
        return (await response.json()) as ReviewManifest;
      })
      .then((loaded) => {
        if (cancelled) return;
        if (
          loaded.schema !== 'ph-a06-ipad-review-data.v1' ||
          loaded.task !== 'TASK-A06' ||
          loaded.source.frameCount !== 451
        ) {
          throw new Error('Unexpected TASK-A06 review-data manifest.');
        }
        setManifest(loaded);
        const saved = loadSavedReview(loaded.assetRevision);
        if (saved) {
          setReviewerReference(saved.reviewerReference);
          setStartedAt(saved.startedAt);
          setDecisions(saved.decisions);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(
            error instanceof Error ? error.message : 'Unable to load review data.',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!manifest) return;
    const payload: SavedReview = {
      reviewerReference,
      startedAt,
      decisions,
    };
    window.localStorage.setItem(
      `ph-a06-review:${manifest.assetRevision}`,
      JSON.stringify(payload),
    );
  }, [manifest, reviewerReference, startedAt, decisions]);

  const structure = manifest?.structures[structureIndex] ?? null;
  const frames = useMemo(
    () => (structure ? supportedFrames(structure) : []),
    [structure],
  );
  const pageCount = Math.max(1, Math.ceil(frames.length / PAGE_SIZE));
  const safePageIndex = Math.min(pageIndex, pageCount - 1);
  const pageFrames = frames.slice(
    safePageIndex * PAGE_SIZE,
    (safePageIndex + 1) * PAGE_SIZE,
  );

  const structureProgress = (candidate: ReviewStructure) => {
    const candidateFrames = supportedFrames(candidate);
    let reviewed = 0;
    let flagged = 0;
    for (const filename of candidateFrames) {
      const decision = decisions[decisionKey(candidate.draftLabel, filename)];
      if (decision) reviewed += 1;
      if (decision?.decision === 'flagged') flagged += 1;
    }
    return { reviewed, flagged, total: candidateFrames.length };
  };

  const setDecision = (
    label: string,
    filename: string,
    decision: ReviewDecisionKind,
  ) => {
    setDecisions((current) => {
      const key = decisionKey(label, filename);
      const existing = current[key];
      const nextDecision: ReviewDecision =
        existing?.note && decision === 'flagged'
          ? { decision, note: existing.note }
          : { decision };
      return { ...current, [key]: nextDecision };
    });
  };

  const setNote = (label: string, filename: string, note: string) => {
    setDecisions((current) => {
      const key = decisionKey(label, filename);
      const existing = current[key];
      const decision = existing?.decision ?? 'flagged';
      const trimmed = note.slice(0, 2000);
      const nextDecision: ReviewDecision =
        trimmed.length > 0 ? { decision, note: trimmed } : { decision };
      return { ...current, [key]: nextDecision };
    });
  };

  const acceptVisiblePage = () => {
    if (!structure) return;
    setDecisions((current) => {
      const next = { ...current };
      for (const filename of pageFrames) {
        const key = decisionKey(structure.draftLabel, filename);
        if (!next[key]) next[key] = { decision: 'accepted' };
      }
      return next;
    });
  };

  const exportReview = () => {
    if (!manifest) return;
    const reviewer = reviewerReference.trim();
    if (!reviewer) {
      setExportError('Enter a reviewer reference before exporting.');
      return;
    }

    const rows = manifest.structures.map((candidate) => {
      const candidateFrames = supportedFrames(candidate);
      const decisionRows = candidateFrames.flatMap((filename) => {
        const decision = decisions[decisionKey(candidate.draftLabel, filename)];
        if (!decision) return [];
        return [
          decision.note
            ? {
                sourceFilename: filename,
                decision: decision.decision,
                note: decision.note,
              }
            : {
                sourceFilename: filename,
                decision: decision.decision,
              },
        ];
      });
      const flaggedFrameCount = decisionRows.filter(
        (row) => row.decision === 'flagged',
      ).length;
      return {
        draftLabel: candidate.draftLabel,
        supportedFrameCount: candidateFrames.length,
        reviewedFrameCount: decisionRows.length,
        flaggedFrameCount,
        complete: decisionRows.length === candidateFrames.length,
        decisions: decisionRows,
      };
    });

    const complete = rows.every((row) => row.complete);
    const flagged = rows.reduce((total, row) => total + row.flaggedFrameCount, 0);
    const payload = {
      schema: 'ph-a06-human-review-session.v1',
      schemaVersion: '1',
      task: 'TASK-A06',
      assetRevision: manifest.assetRevision,
      reviewerReference: reviewer,
      reviewTool: 'Procedural Human A06 iPad Review',
      reviewToolVersion: '1',
      startedAt,
      exportedAt: new Date().toISOString(),
      sessionStatus: complete
        ? flagged > 0
          ? 'complete-with-flags'
          : 'complete-no-flags'
        : 'partial',
      coordinateSpace: {
        kind: 'source-image-stack',
        patientSpaceClaim: false,
        ctRegistrationEstablished: false,
      },
      source: {
        frameCount: 451,
        firstSourceFilename: manifest.source.firstSourceFilename,
        lastSourceFilename: manifest.source.lastSourceFilename,
        cropFilenameShaAggregate: manifest.source.cropFilenameShaAggregate,
      },
      structures: rows,
      claims: {
        humanReviewInputRecorded: true,
        anatomicallyReviewed: false,
        medicalValidation: false,
        patientSpaceGeometry: false,
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
    anchor.download = `a06-human-review-${date}.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setExportError(null);
  };

  const resetReview = () => {
    if (!manifest) return;
    if (!window.confirm('Clear all locally saved TASK-A06 review decisions?')) return;
    window.localStorage.removeItem(`ph-a06-review:${manifest.assetRevision}`);
    setReviewerReference('');
    setStartedAt(new Date().toISOString());
    setDecisions({});
    setOpenFilename(null);
    setExportError(null);
  };

  if (loadError) {
    return (
      <main className="a06-review">
        <section className="a06-review__unavailable">
          <p className="a06-review__eyebrow">TASK-A06 · Human review</p>
          <h1>Review data unavailable</h1>
          <p>{loadError}</p>
          <a href={import.meta.env.BASE_URL}>Return to the 3D preview</a>
        </section>
      </main>
    );
  }

  if (!manifest || !structure) {
    return (
      <main className="a06-review">
        <section className="a06-review__unavailable">
          <p>Loading TASK-A06 source review data…</p>
        </section>
      </main>
    );
  }

  const currentProgress = structureProgress(structure);
  const openDecision = openFilename
    ? decisions[decisionKey(structure.draftLabel, openFilename)]
    : undefined;

  return (
    <main className="a06-review">
      <header className="a06-review__header">
        <div>
          <p className="a06-review__eyebrow">TASK-A06 · Human correction input</p>
          <h1>Distal forearm source / mask review</h1>
          <p className="a06-review__subhead">
            V0 candidate review in source-image-stack coordinates only. This does
            not establish anatomical review, medical validation, Patient Space, or
            Medical Master status.
          </p>
        </div>
        <a className="a06-review__back" href={import.meta.env.BASE_URL}>
          3D preview
        </a>
      </header>

      <section className="a06-review__legal" aria-label="Source attribution">
        <strong>{manifest.distribution.attribution}</strong>
        <span>{manifest.distribution.noEndorsement}</span>
        <span>{manifest.distribution.currencyNotice}</span>
      </section>

      <section className="a06-review__toolbar">
        <label>
          Reviewer reference
          <input
            value={reviewerReference}
            onChange={(event) => setReviewerReference(event.target.value)}
            placeholder="e.g. initials or local reviewer ID"
            autoComplete="off"
          />
        </label>
        <label>
          Mask opacity
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={maskOpacity}
            onChange={(event) => setMaskOpacity(Number(event.target.value))}
          />
          <output>{Math.round(maskOpacity * 100)}%</output>
        </label>
        <div className="a06-review__toolbar-actions">
          <button type="button" onClick={exportReview}>
            Export review JSON
          </button>
          <button type="button" className="a06-review__secondary" onClick={resetReview}>
            Reset local review
          </button>
        </div>
        {exportError && <p className="a06-review__error">{exportError}</p>}
      </section>

      <nav className="a06-review__structures" aria-label="Review structures">
        {manifest.structures.map((candidate, index) => {
          const progress = structureProgress(candidate);
          return (
            <button
              key={candidate.draftLabel}
              type="button"
              aria-pressed={index === structureIndex}
              onClick={() => {
                setStructureIndex(index);
                setPageIndex(0);
                setOpenFilename(null);
              }}
            >
              <strong>{candidate.displayName}</strong>
              <span>
                {progress.reviewed}/{progress.total}
                {progress.flagged > 0 ? ` · ${progress.flagged} flagged` : ''}
              </span>
            </button>
          );
        })}
      </nav>

      <section className="a06-review__structure-info">
        <div>
          <p className="a06-review__eyebrow">{structure.sourceClass}</p>
          <h2>{structure.displayName}</h2>
          <p>{structure.supportStatus}</p>
        </div>
        <div className="a06-review__progress">
          <strong>
            {currentProgress.reviewed} / {currentProgress.total}
          </strong>
          <span>frames reviewed</span>
          {currentProgress.flagged > 0 && (
            <span>{currentProgress.flagged} flagged</span>
          )}
        </div>
      </section>

      <section className="a06-review__page-controls">
        <button
          type="button"
          disabled={safePageIndex === 0}
          onClick={() => setPageIndex((value) => Math.max(0, value - 1))}
        >
          Previous
        </button>
        <span>
          Page {safePageIndex + 1} / {pageCount}
        </span>
        <button
          type="button"
          disabled={safePageIndex >= pageCount - 1}
          onClick={() =>
            setPageIndex((value) => Math.min(pageCount - 1, value + 1))
          }
        >
          Next
        </button>
        <button
          type="button"
          className="a06-review__accept-page"
          onClick={acceptVisiblePage}
        >
          Accept unreviewed frames on this page
        </button>
      </section>

      <section className="a06-review__grid" aria-label="Source frame review grid">
        {pageFrames.map((filename) => {
          const key = decisionKey(structure.draftLabel, filename);
          const decision = decisions[key];
          return (
            <article
              key={filename}
              className="a06-review__tile"
              data-decision={decision?.decision ?? 'unreviewed'}
            >
              <ReviewImage
                filename={filename}
                structure={structure}
                opacity={maskOpacity}
                onOpen={() => setOpenFilename(filename)}
              />
              <div className="a06-review__tile-meta">
                <strong>{filename}</strong>
                <span>{decision?.decision ?? 'unreviewed'}</span>
              </div>
              <div className="a06-review__tile-actions">
                <button
                  type="button"
                  aria-pressed={decision?.decision === 'accepted'}
                  onClick={() =>
                    setDecision(structure.draftLabel, filename, 'accepted')
                  }
                >
                  Accept
                </button>
                <button
                  type="button"
                  aria-pressed={decision?.decision === 'flagged'}
                  onClick={() =>
                    setDecision(structure.draftLabel, filename, 'flagged')
                  }
                >
                  Flag
                </button>
              </div>
            </article>
          );
        })}
      </section>

      {openFilename && (
        <div
          className="a06-review__modal-backdrop"
          role="presentation"
          onClick={() => setOpenFilename(null)}
        >
          <section
            className="a06-review__modal"
            role="dialog"
            aria-modal="true"
            aria-label={`Detailed review of ${openFilename}`}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <p className="a06-review__eyebrow">{structure.displayName}</p>
                <h2>{openFilename}</h2>
              </div>
              <button type="button" onClick={() => setOpenFilename(null)}>
                Close
              </button>
            </header>
            <div className="a06-review__modal-image">
              <ReviewImage
                filename={openFilename}
                structure={structure}
                opacity={maskOpacity}
                onOpen={() => undefined}
              />
            </div>
            <div className="a06-review__modal-actions">
              <button
                type="button"
                aria-pressed={openDecision?.decision === 'accepted'}
                onClick={() =>
                  setDecision(structure.draftLabel, openFilename, 'accepted')
                }
              >
                Accept
              </button>
              <button
                type="button"
                aria-pressed={openDecision?.decision === 'flagged'}
                onClick={() =>
                  setDecision(structure.draftLabel, openFilename, 'flagged')
                }
              >
                Flag for correction
              </button>
            </div>
            <label className="a06-review__note">
              Note for flagged frame
              <textarea
                value={openDecision?.note ?? ''}
                maxLength={2000}
                onChange={(event) =>
                  setNote(structure.draftLabel, openFilename, event.target.value)
                }
                placeholder="Describe the boundary or identity concern."
              />
            </label>
          </section>
        </div>
      )}

      <footer className="a06-review__footer">
        <span>Asset revision: {manifest.assetRevision}</span>
        <span>
          Review decisions stay in this browser until you export the JSON.
        </span>
      </footer>
    </main>
  );
}

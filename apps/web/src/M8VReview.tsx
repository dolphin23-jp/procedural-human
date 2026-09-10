import { useEffect, useMemo, useState } from 'react';
import './m8v-review.css';

type TrackClass =
  | 'ulnar-anchor-linked-continuity'
  | 'anonymous-branch-search'
  | 'anonymous-superficial-search';

type Observation = {
  trackId: string;
  trackClass: TrackClass;
  sourceClassification: string;
  xFullImagePixels: number;
  yFullImagePixels: number;
  depthPixels: number | null;
  directSourceObservation: true;
};

type ReviewFrame = {
  wholeBodyFrameIndex: number;
  sourceFilename: string;
  nominalIndex: number;
  cryosectionSuffix: string;
  cryosection: {
    sourceUrl: string;
    sourcePath: string;
    listedByteSize: number;
    widthPixels: 2048;
    heightPixels: 1216;
  };
  ct: {
    available: boolean;
    sourceUrl: string | null;
    filename: string | null;
    synchronization: string;
    registrationStatus: string;
  };
  observations: Observation[];
};

type ReviewTrack = {
  id: string;
  trackClass: TrackClass;
  sourceClassification: string;
  namedIdentityStatus: string;
  vesselClassStatus: string;
  anchorAnatomicalId: string | null;
  observationCount: number;
  minWholeBodyFrameIndex: number;
  maxWholeBodyFrameIndex: number;
  reviewStatus: string;
};

type Landmark = {
  id: string;
  label: string;
  kind: string;
  evidenceStatus: string;
  sourceClass: string;
  validationLevel: string;
  reviewStatus: string;
  vesselIdentificationUse: string;
};

type Gate = {
  id: string;
  requirement: string;
  status: 'pass' | 'fail' | 'insufficient';
  reason: string;
  evidence: string[];
};

type EvidenceRef = {
  path: string;
  sha256: string;
  schema: string;
};

type ReviewManifest = {
  schema: 'ph-m8v-web-review-manifest.v1';
  task: 'TASK-V07';
  imageDelivery: {
    cryosection: string;
    ct: string;
    contentAddressedAtBrowserRender: boolean;
    snapshotNotice: string;
  };
  sourceTerms: {
    attribution?: string;
    conditions?: string[];
    url?: string;
  };
  surfaceRecord: {
    route: string;
    inputEvidence: EvidenceRef[];
    coordinatePolicy: {
      cryosectionSpace: string;
      ctSpace: string;
      synchronization: string;
      boundedCtRegistrationStart: number;
      boundedCtRegistrationStop: number;
      patientSpaceClaim: false;
    };
    frameCoverage: {
      firstWholeBodyFrameIndex: number;
      lastWholeBodyFrameIndex: number;
      frameCount: number;
      ctProbeLinkedFrameCount: number;
      boundedCtScaffoldFrameCount: number;
    };
    trackCoverage: {
      totalTrackCount: number;
      ulnarAnchorLinkedTrackCount: number;
      anonymousArterialTrackCount: number;
      anonymousSuperficialTrackCount: number;
      directObservationCount: number;
    };
    claims: {
      multimodalReviewSurfaceEstablished: true;
      humanAnatomicalReviewCompleted: false;
      ctCryosectionMedicalRegistrationEstablished: false;
      patientSpaceGeometry: false;
      radialArteryIdentityEstablished: false;
      observedSuperficialVeinStructureEstablished: false;
      namedSuperficialVeinIdentityEstablished: false;
      medicalValidation: false;
      automaticPromotionAllowed: false;
    };
  };
  tracks: ReviewTrack[];
  landmarks: Landmark[];
  unresolvedRequiredLandmarks: string[];
  radialPromotionGates: Gate[];
  superficialPromotionGates: Gate[];
  frames: ReviewFrame[];
};

const CLASS_LABELS: Record<TrackClass, string> = {
  'ulnar-anchor-linked-continuity': 'Ulnar anchor-linked',
  'anonymous-branch-search': 'Anonymous arterial',
  'anonymous-superficial-search': 'Anonymous superficial',
};

function trackClassName(trackClass: TrackClass): string {
  if (trackClass === 'ulnar-anchor-linked-continuity') return 'm8v-track-ulnar';
  if (trackClass === 'anonymous-branch-search') return 'm8v-track-arterial';
  return 'm8v-track-superficial';
}

function gateLabel(status: Gate['status']): string {
  if (status === 'pass') return 'PASS';
  if (status === 'fail') return 'FAIL';
  return 'INSUFFICIENT';
}

export function M8VReview() {
  const [manifest, setManifest] = useState<ReviewManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [showUlnar, setShowUlnar] = useState(true);
  const [showArterial, setShowArterial] = useState(true);
  const [showSuperficial, setShowSuperficial] = useState(true);
  const [cryoError, setCryoError] = useState(false);
  const [ctError, setCtError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const base = import.meta.env.BASE_URL;
    void fetch(`${base}m8v-review-data/manifest.json`, { cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`review manifest HTTP ${response.status}`);
        }
        return (await response.json()) as ReviewManifest;
      })
      .then((value) => {
        if (cancelled) return;
        if (value.schema !== 'ph-m8v-web-review-manifest.v1') {
          throw new Error(`unexpected review manifest schema: ${value.schema}`);
        }
        if (value.frames.length === 0) {
          throw new Error('review manifest contains no frames');
        }
        setManifest(value);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const currentFrame = manifest?.frames[cursor] ?? null;

  useEffect(() => {
    setCryoError(false);
    setCtError(false);
  }, [currentFrame?.wholeBodyFrameIndex]);

  const visibleObservations = useMemo(() => {
    if (currentFrame === null) return [];
    return currentFrame.observations.filter((observation) => {
      if (
        observation.trackClass === 'ulnar-anchor-linked-continuity' &&
        !showUlnar
      ) {
        return false;
      }
      if (observation.trackClass === 'anonymous-branch-search' && !showArterial) {
        return false;
      }
      if (
        observation.trackClass === 'anonymous-superficial-search' &&
        !showSuperficial
      ) {
        return false;
      }
      return selectedTrackId === null || observation.trackId === selectedTrackId;
    });
  }, [
    currentFrame,
    selectedTrackId,
    showArterial,
    showSuperficial,
    showUlnar,
  ]);

  const frameIndexToCursor = useMemo(() => {
    const result = new Map<number, number>();
    manifest?.frames.forEach((frame, index) => {
      result.set(frame.wholeBodyFrameIndex, index);
    });
    return result;
  }, [manifest]);

  const jumpToTrack = (track: ReviewTrack) => {
    setSelectedTrackId(track.id);
    const nextCursor = frameIndexToCursor.get(track.minWholeBodyFrameIndex);
    if (nextCursor !== undefined) setCursor(nextCursor);
  };

  if (error !== null) {
    return (
      <main className="m8v-review-shell">
        <section className="m8v-error-card">
          <h1>M8V review surface unavailable</h1>
          <p>{error}</p>
          <p>
            This does not change any anatomical claim. The review UI is optional;
            committed evidence remains fail-closed.
          </p>
        </section>
      </main>
    );
  }

  if (manifest === null || currentFrame === null) {
    return (
      <main className="m8v-review-shell">
        <section className="m8v-loading-card">
          <h1>M8V multimodal review</h1>
          <p>Loading committed evidence manifest…</p>
        </section>
      </main>
    );
  }

  const ctWithinBoundedScaffold =
    currentFrame.ct.registrationStatus === 'bounded-bone-landmark-scaffold';

  return (
    <main className="m8v-review-shell">
      <header className="m8v-review-header">
        <div>
          <p className="m8v-eyebrow">TASK-V07 · authoring review only</p>
          <h1>M8V multimodal vessel evidence review</h1>
          <p className="m8v-header-copy">
            Cryosection and CT are synchronized only by the provider nominal index.
            Track overlays remain in cryosection source pixels. This surface is not
            Patient Space, medical registration, medical validation, or an identity
            promotion mechanism.
          </p>
        </div>
        <dl className="m8v-header-stats">
          <div>
            <dt>Tracks</dt>
            <dd>{manifest.surfaceRecord.trackCoverage.totalTrackCount}</dd>
          </div>
          <div>
            <dt>Direct observations</dt>
            <dd>{manifest.surfaceRecord.trackCoverage.directObservationCount}</dd>
          </div>
          <div>
            <dt>Review frames</dt>
            <dd>{manifest.surfaceRecord.frameCoverage.frameCount}</dd>
          </div>
        </dl>
      </header>

      <section className="m8v-control-card" aria-label="review navigation">
        <div className="m8v-frame-meta">
          <strong>{currentFrame.sourceFilename}</strong>
          <span>source frame {currentFrame.wholeBodyFrameIndex}</span>
          <span>nominal index {currentFrame.nominalIndex}</span>
          <span>{currentFrame.observations.length} observation(s) on frame</span>
        </div>
        <div className="m8v-slider-row">
          <button
            type="button"
            disabled={cursor === 0}
            onClick={() => setCursor((value) => Math.max(0, value - 1))}
          >
            Previous
          </button>
          <input
            aria-label="review frame"
            type="range"
            min={0}
            max={manifest.frames.length - 1}
            value={cursor}
            onChange={(event) => setCursor(Number(event.currentTarget.value))}
          />
          <button
            type="button"
            disabled={cursor === manifest.frames.length - 1}
            onClick={() =>
              setCursor((value) => Math.min(manifest.frames.length - 1, value + 1))
            }
          >
            Next
          </button>
        </div>
        <div className="m8v-filter-row">
          <label>
            <input
              type="checkbox"
              checked={showUlnar}
              onChange={(event) => setShowUlnar(event.currentTarget.checked)}
            />
            Ulnar anchor-linked
          </label>
          <label>
            <input
              type="checkbox"
              checked={showArterial}
              onChange={(event) => setShowArterial(event.currentTarget.checked)}
            />
            Anonymous arterial
          </label>
          <label>
            <input
              type="checkbox"
              checked={showSuperficial}
              onChange={(event) => setShowSuperficial(event.currentTarget.checked)}
            />
            Anonymous superficial
          </label>
          {selectedTrackId !== null ? (
            <button type="button" onClick={() => setSelectedTrackId(null)}>
              Clear track focus
            </button>
          ) : null}
        </div>
      </section>

      <section className="m8v-image-grid">
        <article className="m8v-image-card">
          <div className="m8v-image-title-row">
            <div>
              <p className="m8v-eyebrow">Cryosection</p>
              <h2>{currentFrame.sourceFilename}</h2>
            </div>
            <span className="m8v-status-chip">source-image-stack</span>
          </div>
          <div className="m8v-image-stage m8v-cryo-stage">
            {cryoError ? (
              <div className="m8v-image-placeholder">
                Live provider image could not be loaded. No substitute image is
                used.
              </div>
            ) : (
              <img
                src={currentFrame.cryosection.sourceUrl}
                alt={`Visible Human Female cryosection ${currentFrame.sourceFilename}`}
                onError={() => setCryoError(true)}
              />
            )}
            {!cryoError ? (
              <svg
                className="m8v-overlay"
                viewBox="0 0 2048 1216"
                role="img"
                aria-label="candidate track observations in cryosection source pixels"
              >
                {visibleObservations.map((observation) => {
                  const selected = observation.trackId === selectedTrackId;
                  return (
                    <g key={`${observation.trackId}-${currentFrame.wholeBodyFrameIndex}`}>
                      <circle
                        className={`${trackClassName(observation.trackClass)}${selected ? ' m8v-selected-observation' : ''}`}
                        cx={observation.xFullImagePixels}
                        cy={observation.yFullImagePixels}
                        r={selected ? 16 : 11}
                      />
                      <circle
                        className="m8v-observation-core"
                        cx={observation.xFullImagePixels}
                        cy={observation.yFullImagePixels}
                        r={3}
                      />
                    </g>
                  );
                })}
              </svg>
            ) : null}
          </div>
          <p className="m8v-caption">
            Overlay coordinates are direct TASK-V04 cryosection source-pixel
            observations. They are not transformed into CT space.
          </p>
        </article>

        <article className="m8v-image-card">
          <div className="m8v-image-title-row">
            <div>
              <p className="m8v-eyebrow">Same-subject CT</p>
              <h2>{currentFrame.ct.filename ?? 'No bounded probe image'}</h2>
            </div>
            <span
              className={`m8v-status-chip${ctWithinBoundedScaffold ? ' m8v-status-supported' : ''}`}
            >
              {ctWithinBoundedScaffold ? 'bounded scaffold' : 'not registered'}
            </span>
          </div>
          <div className="m8v-image-stage m8v-ct-stage">
            {currentFrame.ct.available && currentFrame.ct.sourceUrl !== null ? (
              ctError ? (
                <div className="m8v-image-placeholder">
                  Live CT image could not be loaded. No substitute image is used.
                </div>
              ) : (
                <img
                  src={currentFrame.ct.sourceUrl}
                  alt={`Visible Human Female CT nominal index ${currentFrame.nominalIndex}`}
                  onError={() => setCtError(true)}
                />
              )
            ) : (
              <div className="m8v-image-placeholder">
                CT is intentionally unavailable outside the existing bounded probe
                range in this review surface.
              </div>
            )}
          </div>
          <p className="m8v-caption">
            {currentFrame.ct.registrationStatus}. Shared nominal index is an
            inspection aid only; the CT panel has its own source-pixel space.
          </p>
        </article>
      </section>

      <section className="m8v-review-grid">
        <article className="m8v-panel">
          <div className="m8v-panel-heading">
            <div>
              <p className="m8v-eyebrow">Track graph</p>
              <h2>Candidate tracks</h2>
            </div>
            <span>{selectedTrackId ?? 'all tracks'}</span>
          </div>
          <div className="m8v-track-list">
            {manifest.tracks.map((track) => (
              <button
                type="button"
                key={track.id}
                className={`m8v-track-row ${trackClassName(track.trackClass)}${selectedTrackId === track.id ? ' m8v-track-row-selected' : ''}`}
                onClick={() => jumpToTrack(track)}
              >
                <span>
                  <strong>{track.id}</strong>
                  <small>{CLASS_LABELS[track.trackClass]}</small>
                </span>
                <span>
                  {track.observationCount} obs · {track.minWholeBodyFrameIndex}–
                  {track.maxWholeBodyFrameIndex}
                </span>
              </button>
            ))}
          </div>
        </article>

        <article className="m8v-panel">
          <div className="m8v-panel-heading">
            <div>
              <p className="m8v-eyebrow">Landmarks</p>
              <h2>Evidence constraints</h2>
            </div>
          </div>
          <div className="m8v-landmark-list">
            {manifest.landmarks.map((landmark) => (
              <div className="m8v-landmark-row" key={landmark.id}>
                <span>
                  <strong>{landmark.label}</strong>
                  <small>{landmark.id}</small>
                </span>
                <span className={`m8v-evidence-${landmark.evidenceStatus}`}>
                  {landmark.evidenceStatus}
                </span>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="m8v-review-grid">
        <GatePanel title="Radial artery identity" gates={manifest.radialPromotionGates} />
        <GatePanel
          title="Superficial vein structure"
          gates={manifest.superficialPromotionGates}
        />
      </section>

      <section className="m8v-panel m8v-provenance-panel">
        <div className="m8v-panel-heading">
          <div>
            <p className="m8v-eyebrow">Provenance</p>
            <h2>Review boundary</h2>
          </div>
        </div>
        <p>{manifest.imageDelivery.snapshotNotice}</p>
        <p>
          Cryosection: {manifest.surfaceRecord.coordinatePolicy.cryosectionSpace} ·
          CT: {manifest.surfaceRecord.coordinatePolicy.ctSpace} · synchronization:{' '}
          {manifest.surfaceRecord.coordinatePolicy.synchronization}.
        </p>
        <div className="m8v-provenance-list">
          {manifest.surfaceRecord.inputEvidence.map((evidence) => (
            <div key={evidence.path}>
              <strong>{evidence.schema}</strong>
              <span>{evidence.path}</span>
              <code>{evidence.sha256}</code>
            </div>
          ))}
        </div>
        <p className="m8v-terms">
          {manifest.sourceTerms.attribution ?? 'U.S. National Library of Medicine'}.
          Provider snapshot terms and no-endorsement notice remain applicable.
        </p>
      </section>
    </main>
  );
}

function GatePanel({ title, gates }: { title: string; gates: Gate[] }) {
  return (
    <article className="m8v-panel">
      <div className="m8v-panel-heading">
        <div>
          <p className="m8v-eyebrow">Promotion gates</p>
          <h2>{title}</h2>
        </div>
      </div>
      <div className="m8v-gate-list">
        {gates.map((gate) => (
          <details key={gate.id} className={`m8v-gate m8v-gate-${gate.status}`}>
            <summary>
              <span>{gate.id}</span>
              <strong>{gateLabel(gate.status)}</strong>
            </summary>
            <p>{gate.reason}</p>
            <ul>
              {gate.evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </article>
  );
}

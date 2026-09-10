import { useEffect, useMemo, useState } from 'react';
import './m8v-adjudication.css';

type TrackClass =
  | 'ulnar-anchor-linked-continuity'
  | 'anonymous-branch-search'
  | 'anonymous-superficial-search';

type Observation = {
  trackId: string;
  trackClass: TrackClass;
  xFullImagePixels: number;
  yFullImagePixels: number;
  directSourceObservation: true;
};

type ReviewFrame = {
  wholeBodyFrameIndex: number;
  sourceFilename: string;
  nominalIndex: number;
  cryosection: { sourceUrl: string };
  ct: {
    available: boolean;
    sourceUrl: string | null;
    filename: string | null;
    registrationStatus: string;
  };
  observations: Observation[];
};

type ReviewTrack = {
  id: string;
  trackClass: TrackClass;
  minWholeBodyFrameIndex: number;
  maxWholeBodyFrameIndex: number;
  observationCount: number;
};

type EvidenceRef = {
  path: string;
  schema: string;
  sha256: string;
};

type ReviewManifest = {
  schema: 'ph-m8v-web-review-manifest.v1';
  surfaceRecord: {
    inputEvidence: EvidenceRef[];
  };
  tracks: ReviewTrack[];
  frames: ReviewFrame[];
};

type LedgerClaim = {
  id: string;
  domain: 'radial-artery' | 'superficial-vein' | 'named-superficial-vein';
  requirement: string;
  state: 'supported' | 'conflicting' | 'missing' | 'blocked' | 'unresolved';
  humanReviewStatus: 'not-reviewed' | 'accepted' | 'rejected' | 'unresolved';
  validationLevel: 'V0' | 'V1' | 'V2' | 'V3' | 'V4';
};

type Ledger = {
  schema: 'ph-m8v-evidence-ledger.v1';
  sourceEvidence: Array<EvidenceRef & { role: string }>;
  claims: LedgerClaim[];
  decision: {
    ledgerState: string;
    radialPromotionReady: boolean;
    superficialStructurePromotionReady: boolean;
    namedSuperficialPromotionReady: boolean;
  };
};

type Verdict = 'accepted' | 'rejected' | 'unresolved';

type DraftDecision = {
  verdict: Verdict;
  evidenceFrameIndices: number[];
  note: string;
};

const CLAIM_KIND: Record<
  string,
  | 'track-continuity'
  | 'vessel-class'
  | 'branch-topology'
  | 'landmark-relationship'
  | 'competitor-resolution'
  | 'radial-artery-identity'
  | 'superficial-vein-structure'
  | 'named-superficial-vein-identity'
> = {
  'radial.gate.same-subject-anchor': 'radial-artery-identity',
  'radial.gate.continuity': 'track-continuity',
  'radial.gate.branch-topology': 'branch-topology',
  'radial.gate.landmark-relationships': 'landmark-relationship',
  'radial.gate.competitor-resolution': 'competitor-resolution',
  'radial.gate.human-review': 'radial-artery-identity',
  'superficial.gate.direct-extent': 'track-continuity',
  'superficial.gate.continuity': 'track-continuity',
  'superficial.gate.subcutaneous-relationship': 'landmark-relationship',
  'superficial.gate.vein-class': 'vessel-class',
  'superficial.gate.competitor-resolution': 'competitor-resolution',
  'superficial.gate.human-review': 'superficial-vein-structure',
  'superficial.structure.observed': 'superficial-vein-structure',
  'superficial.identity.named-topology': 'branch-topology',
  'superficial.identity.named': 'named-superficial-vein-identity',
};

function sessionStorageKey(surfaceHash: string): string {
  return `ph-m8v-adjudication:${surfaceHash}`;
}

function targetForClaim(
  claim: LedgerClaim,
  radialTrackId: string,
  superficialTrackId: string,
): string {
  return claim.domain === 'radial-artery' ? radialTrackId : superficialTrackId;
}

function imageClass(trackClass: TrackClass): string {
  if (trackClass === 'anonymous-branch-search') return 'm8v-adj-marker-radial';
  if (trackClass === 'anonymous-superficial-search') return 'm8v-adj-marker-superficial';
  return 'm8v-adj-marker-ulnar';
}

export function M8VAdjudication() {
  const [manifest, setManifest] = useState<ReviewManifest | null>(null);
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [reviewerReference, setReviewerReference] = useState('');
  const [startedAt, setStartedAt] = useState(() => new Date().toISOString());
  const [radialTrackId, setRadialTrackId] = useState('');
  const [superficialTrackId, setSuperficialTrackId] = useState('');
  const [decisions, setDecisions] = useState<Record<string, DraftDecision>>({});
  const [exportError, setExportError] = useState<string | null>(null);
  const [cryoError, setCryoError] = useState(false);
  const [ctError, setCtError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const base = import.meta.env.BASE_URL;
    void Promise.all([
      fetch(`${base}m8v-review-data/manifest.json`, { cache: 'no-store' }),
      fetch(`${base}m8v-review-data/evidence-ledger.json`, { cache: 'no-store' }),
    ])
      .then(async ([manifestResponse, ledgerResponse]) => {
        if (!manifestResponse.ok) {
          throw new Error(`review manifest HTTP ${manifestResponse.status}`);
        }
        if (!ledgerResponse.ok) {
          throw new Error(`evidence ledger HTTP ${ledgerResponse.status}`);
        }
        return [
          (await manifestResponse.json()) as ReviewManifest,
          (await ledgerResponse.json()) as Ledger,
        ] as const;
      })
      .then(([loadedManifest, loadedLedger]) => {
        if (cancelled) return;
        if (loadedManifest.schema !== 'ph-m8v-web-review-manifest.v1') {
          throw new Error('unexpected review manifest schema');
        }
        if (loadedLedger.schema !== 'ph-m8v-evidence-ledger.v1') {
          throw new Error('unexpected evidence ledger schema');
        }
        if (loadedManifest.frames.length === 0) {
          throw new Error('review manifest contains no frames');
        }
        setManifest(loadedManifest);
        setLedger(loadedLedger);
        const radial = loadedManifest.tracks.find(
          (track) => track.trackClass === 'anonymous-branch-search',
        );
        const superficial = loadedManifest.tracks.find(
          (track) => track.trackClass === 'anonymous-superficial-search',
        );
        if (!radial || !superficial) {
          throw new Error('required candidate track classes are unavailable');
        }
        setRadialTrackId(radial.id);
        setSuperficialTrackId(superficial.id);

        const surface = loadedLedger.sourceEvidence.find(
          (source) => source.role === 'multimodal-review-surface',
        );
        if (!surface) throw new Error('ledger lacks TASK-V07 evidence reference');
        const saved = window.localStorage.getItem(sessionStorageKey(surface.sha256));
        if (saved) {
          const parsed = JSON.parse(saved) as {
            reviewerReference?: string;
            startedAt?: string;
            radialTrackId?: string;
            superficialTrackId?: string;
            decisions?: Record<string, DraftDecision>;
          };
          setReviewerReference(parsed.reviewerReference ?? '');
          setStartedAt(parsed.startedAt ?? new Date().toISOString());
          if (parsed.radialTrackId) setRadialTrackId(parsed.radialTrackId);
          if (parsed.superficialTrackId) {
            setSuperficialTrackId(parsed.superficialTrackId);
          }
          setDecisions(parsed.decisions ?? {});
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const v07Evidence = ledger?.sourceEvidence.find(
    (source) => source.role === 'multimodal-review-surface',
  );

  useEffect(() => {
    if (!v07Evidence) return;
    window.localStorage.setItem(
      sessionStorageKey(v07Evidence.sha256),
      JSON.stringify({
        reviewerReference,
        startedAt,
        radialTrackId,
        superficialTrackId,
        decisions,
      }),
    );
  }, [
    decisions,
    radialTrackId,
    reviewerReference,
    startedAt,
    superficialTrackId,
    v07Evidence,
  ]);

  const currentFrame = manifest?.frames[cursor] ?? null;
  useEffect(() => {
    setCryoError(false);
    setCtError(false);
  }, [currentFrame?.wholeBodyFrameIndex]);

  const radialTracks = useMemo(
    () =>
      manifest?.tracks.filter(
        (track) => track.trackClass === 'anonymous-branch-search',
      ) ?? [],
    [manifest],
  );
  const superficialTracks = useMemo(
    () =>
      manifest?.tracks.filter(
        (track) => track.trackClass === 'anonymous-superficial-search',
      ) ?? [],
    [manifest],
  );

  const selectedObservations = useMemo(() => {
    if (!currentFrame) return [];
    return currentFrame.observations.filter(
      (observation) =>
        observation.trackId === radialTrackId ||
        observation.trackId === superficialTrackId,
    );
  }, [currentFrame, radialTrackId, superficialTrackId]);

  const frameCursorByIndex = useMemo(() => {
    const map = new Map<number, number>();
    manifest?.frames.forEach((frame, index) => {
      map.set(frame.wholeBodyFrameIndex, index);
    });
    return map;
  }, [manifest]);

  const jumpToTrack = (trackId: string) => {
    const track = manifest?.tracks.find((candidate) => candidate.id === trackId);
    if (!track) return;
    const next = frameCursorByIndex.get(track.minWholeBodyFrameIndex);
    if (next !== undefined) setCursor(next);
  };

  const setVerdict = (claimId: string, verdict: Verdict) => {
    setDecisions((current) => ({
      ...current,
      [claimId]: {
        verdict,
        evidenceFrameIndices: current[claimId]?.evidenceFrameIndices ?? [],
        note: current[claimId]?.note ?? '',
      },
    }));
  };

  const setNote = (claimId: string, note: string) => {
    setDecisions((current) => {
      const existing = current[claimId] ?? {
        verdict: 'unresolved' as const,
        evidenceFrameIndices: [],
        note: '',
      };
      return {
        ...current,
        [claimId]: { ...existing, note: note.slice(0, 4000) },
      };
    });
  };

  const toggleCurrentFrame = (claimId: string) => {
    if (!currentFrame) return;
    setDecisions((current) => {
      const existing = current[claimId] ?? {
        verdict: 'unresolved' as const,
        evidenceFrameIndices: [],
        note: '',
      };
      const frame = currentFrame.wholeBodyFrameIndex;
      const present = existing.evidenceFrameIndices.includes(frame);
      const evidenceFrameIndices = present
        ? existing.evidenceFrameIndices.filter((value) => value !== frame)
        : [...existing.evidenceFrameIndices, frame].sort((a, b) => a - b);
      return {
        ...current,
        [claimId]: { ...existing, evidenceFrameIndices },
      };
    });
  };

  const exportSession = () => {
    if (!manifest || !ledger || !v07Evidence) return;
    const reviewer = reviewerReference.trim();
    if (!reviewer) {
      setExportError('Enter a reviewer reference before export.');
      return;
    }
    const reviewedClaims = ledger.claims.filter((claim) => decisions[claim.id]);
    if (reviewedClaims.length === 0) {
      setExportError('Record at least one claim decision before export.');
      return;
    }
    const acceptedWithoutFrames = reviewedClaims.find(
      (claim) =>
        decisions[claim.id].verdict === 'accepted' &&
        decisions[claim.id].evidenceFrameIndices.length === 0,
    );
    if (acceptedWithoutFrames) {
      setExportError(
        `Accepted claim ${acceptedWithoutFrames.id} needs at least one evidence frame.`,
      );
      return;
    }
    if (!radialTrackId || !superficialTrackId) {
      setExportError('Select both radial and superficial candidate targets.');
      return;
    }

    const payload = {
      schema: 'ph-m8v-human-adjudication-session.v1',
      schemaVersion: '1',
      task: 'TASK-V08',
      reviewerReference: reviewer,
      startedAt,
      exportedAt: new Date().toISOString(),
      reviewTool: {
        name: 'Procedural Human M8V Adjudication',
        version: '1',
        route: '?m8v-adjudicate=1',
      },
      reviewSurface: {
        path: 'authoring/outputs/m8v-v07-multimodal-review-surface-20260911.json',
        schema: 'ph-m8v-multimodal-review-surface.v1',
        sha256: v07Evidence.sha256,
      },
      evidenceSnapshot: manifest.surfaceRecord.inputEvidence,
      decisions: reviewedClaims.map((claim) => {
        const decision = decisions[claim.id];
        const result: {
          claimId: string;
          kind: (typeof CLAIM_KIND)[string];
          targetId: string;
          verdict: Verdict;
          evidenceFrameIndices: number[];
          note?: string;
        } = {
          claimId: claim.id,
          kind: CLAIM_KIND[claim.id],
          targetId: targetForClaim(
            claim,
            radialTrackId,
            superficialTrackId,
          ),
          verdict: decision.verdict,
          evidenceFrameIndices: decision.evidenceFrameIndices,
        };
        const note = decision.note.trim();
        if (note) result.note = note;
        return result;
      }),
      claims: {
        humanReviewInputRecorded: true,
        medicalValidation: false,
        procedureRoleEstablished: false,
        automaticPromotionAllowed: false,
      },
    };

    const blob = new Blob([JSON.stringify(payload, null, 2) + '\n'], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `m8v-human-adjudication-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setExportError(null);
  };

  const resetSession = () => {
    if (!v07Evidence) return;
    if (!window.confirm('Clear locally saved M8V adjudication decisions?')) return;
    window.localStorage.removeItem(sessionStorageKey(v07Evidence.sha256));
    setReviewerReference('');
    setStartedAt(new Date().toISOString());
    setDecisions({});
    setExportError(null);
  };

  if (error) {
    return (
      <main className="m8v-adj-shell">
        <section className="m8v-adj-card">
          <h1>M8V adjudication unavailable</h1>
          <p>{error}</p>
          <p>No evidence claim has been changed.</p>
        </section>
      </main>
    );
  }

  if (!manifest || !ledger || !currentFrame || !v07Evidence) {
    return (
      <main className="m8v-adj-shell">
        <section className="m8v-adj-card">
          <h1>M8V anatomical adjudication</h1>
          <p>Loading immutable evidence references…</p>
        </section>
      </main>
    );
  }

  return (
    <main className="m8v-adj-shell">
      <header className="m8v-adj-header">
        <div>
          <p className="m8v-adj-eyebrow">TASK-V08 · explicit human evidence</p>
          <h1>Vessel identity adjudication</h1>
          <p>
            Each claim is reviewed independently. Accepting one claim does not
            accept the remaining gates, confer medical validation, establish
            Patient Space, or create a procedure role.
          </p>
        </div>
        <a href={`${import.meta.env.BASE_URL}?m8v-review=1`}>
          Open full V07 review surface
        </a>
      </header>

      <section className="m8v-adj-card m8v-adj-session">
        <label>
          Reviewer reference
          <input
            value={reviewerReference}
            maxLength={200}
            onChange={(event) => setReviewerReference(event.currentTarget.value)}
            placeholder="e.g. reviewer initials or internal reference"
          />
        </label>
        <label>
          Radial candidate target
          <select
            value={radialTrackId}
            onChange={(event) => {
              setRadialTrackId(event.currentTarget.value);
              jumpToTrack(event.currentTarget.value);
            }}
          >
            {radialTracks.map((track) => (
              <option key={track.id} value={track.id}>
                {track.id} · {track.observationCount} observations
              </option>
            ))}
          </select>
        </label>
        <label>
          Superficial candidate target
          <select
            value={superficialTrackId}
            onChange={(event) => {
              setSuperficialTrackId(event.currentTarget.value);
              jumpToTrack(event.currentTarget.value);
            }}
          >
            {superficialTracks.map((track) => (
              <option key={track.id} value={track.id}>
                {track.id} · {track.observationCount} observations
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="m8v-adj-card">
        <div className="m8v-adj-nav">
          <button
            type="button"
            disabled={cursor === 0}
            onClick={() => setCursor((value) => Math.max(0, value - 1))}
          >
            Previous
          </button>
          <input
            aria-label="evidence frame"
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
        <p>
          <strong>{currentFrame.sourceFilename}</strong> · source frame{' '}
          {currentFrame.wholeBodyFrameIndex} · nominal index{' '}
          {currentFrame.nominalIndex}
        </p>
        <div className="m8v-adj-images">
          <div className="m8v-adj-image-stage">
            {cryoError ? (
              <p>Provider cryosection unavailable; no substitute is used.</p>
            ) : (
              <img
                src={currentFrame.cryosection.sourceUrl}
                alt={`Cryosection ${currentFrame.sourceFilename}`}
                onError={() => setCryoError(true)}
              />
            )}
            {!cryoError ? (
              <svg viewBox="0 0 2048 1216" aria-label="selected candidate observations">
                {selectedObservations.map((observation) => (
                  <circle
                    key={observation.trackId}
                    className={imageClass(observation.trackClass)}
                    cx={observation.xFullImagePixels}
                    cy={observation.yFullImagePixels}
                    r={15}
                  />
                ))}
              </svg>
            ) : null}
          </div>
          <div className="m8v-adj-image-stage m8v-adj-ct-stage">
            {currentFrame.ct.available && currentFrame.ct.sourceUrl ? (
              ctError ? (
                <p>Provider CT unavailable; no substitute is used.</p>
              ) : (
                <img
                  src={currentFrame.ct.sourceUrl}
                  alt={`CT ${currentFrame.ct.filename ?? currentFrame.nominalIndex}`}
                  onError={() => setCtError(true)}
                />
              )
            ) : (
              <p>CT outside the bounded probe range.</p>
            )}
          </div>
        </div>
        <p className="m8v-adj-muted">
          CT status: {currentFrame.ct.registrationStatus}. Selected markers are
          cryosection source-pixel observations only and are not projected into
          CT space.
        </p>
      </section>

      <section className="m8v-adj-claims">
        {ledger.claims.map((claim) => {
          const decision = decisions[claim.id];
          const targetId = targetForClaim(
            claim,
            radialTrackId,
            superficialTrackId,
          );
          const currentRecorded =
            decision?.evidenceFrameIndices.includes(
              currentFrame.wholeBodyFrameIndex,
            ) ?? false;
          const targetObservedHere = currentFrame.observations.some(
            (observation) => observation.trackId === targetId,
          );
          return (
            <article className="m8v-adj-card m8v-adj-claim" key={claim.id}>
              <div className="m8v-adj-claim-heading">
                <div>
                  <p className="m8v-adj-eyebrow">{claim.domain}</p>
                  <h2>{claim.id}</h2>
                </div>
                <span className={`m8v-adj-state m8v-adj-state-${claim.state}`}>
                  current: {claim.state}
                </span>
              </div>
              <p>{claim.requirement}</p>
              <p className="m8v-adj-muted">Target: {targetId}</p>
              <div className="m8v-adj-verdicts">
                {(['accepted', 'rejected', 'unresolved'] as const).map(
                  (verdict) => (
                    <button
                      key={verdict}
                      type="button"
                      aria-pressed={decision?.verdict === verdict}
                      onClick={() => setVerdict(claim.id, verdict)}
                    >
                      {verdict}
                    </button>
                  ),
                )}
              </div>
              <button
                className="m8v-adj-evidence-button"
                type="button"
                onClick={() => toggleCurrentFrame(claim.id)}
              >
                {currentRecorded ? 'Remove current frame' : 'Add current frame'}
                {targetObservedHere ? ' · target observed here' : ' · context frame'}
              </button>
              <p className="m8v-adj-muted">
                Evidence frames:{' '}
                {decision?.evidenceFrameIndices.length
                  ? decision.evidenceFrameIndices.join(', ')
                  : 'none'}
              </p>
              <label>
                Review note
                <textarea
                  rows={3}
                  maxLength={4000}
                  value={decision?.note ?? ''}
                  onChange={(event) => setNote(claim.id, event.currentTarget.value)}
                />
              </label>
            </article>
          );
        })}
      </section>

      <section className="m8v-adj-card m8v-adj-export">
        <div>
          <h2>Export claim-level review receipt</h2>
          <p>
            The exported JSON carries the exact TASK-V07 hash and evidence
            snapshot. A later ledger build rejects it if those inputs have
            changed.
          </p>
          <p className="m8v-adj-muted">TASK-V07 SHA-256: {v07Evidence.sha256}</p>
        </div>
        <div className="m8v-adj-export-actions">
          <button type="button" onClick={exportSession}>
            Export adjudication JSON
          </button>
          <button type="button" onClick={resetSession}>
            Reset local session
          </button>
        </div>
        {exportError ? <p className="m8v-adj-error">{exportError}</p> : null}
      </section>
    </main>
  );
}

from pathlib import Path


TARGET = Path("apps/web/src/M8VAdjudication.tsx")


def main() -> None:
    text = TARGET.read_text()

    old = '''    const acceptedWithoutFrames = reviewedClaims.find(
      (claim) =>
        decisions[claim.id].verdict === 'accepted' &&
        decisions[claim.id].evidenceFrameIndices.length === 0,
    );
'''
    new = '''    const acceptedWithoutFrames = reviewedClaims.find((claim) => {
      const decision = decisions[claim.id];
      return (
        decision?.verdict === 'accepted' &&
        decision.evidenceFrameIndices.length === 0
      );
    });
'''
    if old not in text and new not in text:
        raise RuntimeError("acceptedWithoutFrames block not found")
    text = text.replace(old, new, 1)

    old = '''      decisions: reviewedClaims.map((claim) => {
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
'''
    new = '''      decisions: reviewedClaims.map((claim) => {
        const decision = decisions[claim.id];
        const kind = CLAIM_KIND[claim.id];
        if (!decision || !kind) {
          throw new Error(`Review state is inconsistent for claim ${claim.id}.`);
        }
        const result: {
          claimId: string;
          kind: (typeof CLAIM_KIND)[string];
          targetId: string;
          verdict: Verdict;
          evidenceFrameIndices: number[];
          note?: string;
        } = {
          claimId: claim.id,
          kind,
          targetId: targetForClaim(
            claim,
            radialTrackId,
            superficialTrackId,
          ),
          verdict: decision.verdict,
          evidenceFrameIndices: decision.evidenceFrameIndices,
        };
'''
    if old not in text and new not in text:
        raise RuntimeError("reviewedClaims map block not found")
    text = text.replace(old, new, 1)

    TARGET.write_text(text)
    print("TASK-V08 TypeScript fail-closed patch applied")


if __name__ == "__main__":
    main()

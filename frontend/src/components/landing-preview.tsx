"use client";

type LandingPreviewProps = {
  onEnter: () => void;
};

export function LandingPreview({ onEnter }: LandingPreviewProps) {
  return (
    <div className="landing-preview-wrap">
      <div className="landing-preview" aria-label="Animated preview of the A-Brain world">
        <div className="preview-topline">
          <span>ABRAIN WORLD</span>
          <span className="preview-live">
            <i aria-hidden="true" /> LIVE PREVIEW
          </span>
        </div>
        <div className="preview-map" aria-hidden="true">
          <span className="preview-road preview-road-horizontal" />
          <span className="preview-road preview-road-vertical" />
          <span className="preview-tree preview-tree-one" />
          <span className="preview-tree preview-tree-two" />
          <span className="preview-house preview-house-one" />
          <span className="preview-house preview-house-two" />
          <span className="preview-vault">
            <span className="preview-vault-core" />
            <b>BRAIN VAULT</b>
          </span>
          <span className="preview-path" />
          <span className="preview-memory-shard preview-shard-one" />
          <span className="preview-memory-shard preview-shard-two" />
          <span className="preview-agent">
            <span className="preview-agent-aura" />
            <span className="preview-agent-body">
              <i />
              <i />
            </span>
          </span>
          <span className="preview-sign">
            SESSION 02
            <br />
            RESTORED
          </span>
        </div>
        <div className="preview-bottomline">
          <span>
            <b>01</b> body
          </span>
          <span>
            <b>01</b> brain
          </span>
          <span>
            <b>∞</b> sessions
          </span>
        </div>
      </div>
      <button className="preview-cta" type="button" onClick={onEnter}>
        <span>Enter A-Brain World</span>
        <span aria-hidden="true">↗</span>
      </button>
    </div>
  );
}

import { FormEvent, useState } from "react";
import {
  IngestRequest,
  MAX_TEXT_LENGTH,
  validateIntake,
} from "../services/api";
import { ScenarioPreset } from "../services/demo";
import { Button, Card } from "./ui";

interface InputFormProps {
  onSubmit: (req: IngestRequest) => void;
  isSubmitting: boolean;
  presets?: ScenarioPreset[]; // guided demo (#43): fill the text only
}

// Patient-facing intake form. Only patient-provided input lives here; runtime/backend settings do not.
export default function InputForm({ onSubmit, isSubmitting, presets = [] }: InputFormProps) {
  const [text, setText] = useState("");
  const [activePreset, setActivePreset] = useState<ScenarioPreset | null>(null);
  const [consent, setConsent] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;

    const req = { text, consent_granted: consent };
    const error = validateIntake(req);
    setLocalError(error);
    if (error) return;

    onSubmit(req);
  }

  return (
    <Card as="form" className="intake-form" onSubmit={handleSubmit} noValidate>
      <h2>Tell us what brings you in</h2>
      <p className="muted">
        Describe your symptoms in your own words: what you are feeling, when it
        started, and anything that makes it better or worse.
      </p>

      {presets.length > 0 && (
        <div className="presets" role="group" aria-label="Synthetic demo scenarios">
          <span className="muted">Try a synthetic scenario:</span>
          {presets.map((p) => (
            <Button
              key={p.id}
              size="sm"
              disabled={isSubmitting}
              aria-pressed={activePreset?.id === p.id}
              onClick={() => {
                // Fills the text only; consent and validation stay with the patient
                setText(p.text);
                setActivePreset(p);
                setLocalError(null);
              }}
            >
              {p.label}
            </Button>
          ))}
          {activePreset && (
            <p className="muted" data-testid="preset-expectation">
              Expected: {activePreset.expect}
            </p>
          )}
        </div>
      )}

      <label htmlFor="symptoms" className="field-label">
        Your symptoms
      </label>
      <textarea
        id="symptoms"
        name="symptoms"
        rows={7}
        value={text}
        maxLength={MAX_TEXT_LENGTH}
        onChange={(e) => setText(e.target.value)}
        disabled={isSubmitting}
        aria-invalid={localError ? true : undefined}
        aria-describedby="symptoms-hint symptoms-error"
        placeholder="e.g. I've had a sore throat and a mild fever for two days, and I feel more tired than usual."
      />
      <div id="symptoms-hint" className="field-hint">
        <span>Demo only: please use made-up details, not real personal information.</span>
        <span>
          {text.length}/{MAX_TEXT_LENGTH}
        </span>
      </div>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          disabled={isSubmitting}
        />
        <span>
          I consent to this information being processed to prepare a summary for
          my care team.
        </span>
      </label>

      <div id="symptoms-error" aria-live="polite">
        {localError && <p className="inline-error">{localError}</p>}
      </div>

      <Button type="submit" variant="primary" disabled={isSubmitting}>
        {isSubmitting ? "Submitting…" : "Submit intake"}
      </Button>
    </Card>
  );
}

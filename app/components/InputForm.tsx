import { FormEvent, useState } from "react";
import {
  IngestRequest,
  MAX_TEXT_LENGTH,
  validateIntake,
} from "../services/api";

interface InputFormProps {
  onSubmit: (req: IngestRequest) => void;
  isSubmitting: boolean;
}

// Patient-facing intake form. Only patient-provided input lives here; runtime/backend settings do not.
export default function InputForm({ onSubmit, isSubmitting }: InputFormProps) {
  const [text, setText] = useState("");
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
    <form className="card intake-form" onSubmit={handleSubmit} noValidate>
      <h2>Tell us what brings you in</h2>
      <p className="muted">
        Describe your symptoms in your own words: what you are feeling, when it
        started, and anything that makes it better or worse.
      </p>

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

      <button type="submit" className="primary" disabled={isSubmitting}>
        {isSubmitting ? "Submitting…" : "Submit intake"}
      </button>
    </form>
  );
}

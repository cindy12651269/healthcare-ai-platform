import { FormEvent, Ref } from "react";
import { MAX_TEXT_LENGTH } from "../services/api";
import { ScenarioPreset } from "../services/demo";
import { Button, Card } from "./ui";

// Which field a submission error belongs to, so it is linked with aria-describedby and focused (#70)
export type FieldError = { field: "symptoms" | "consent"; message: string } | null;

export interface IntakeFormValues {
  text: string;
  consent: boolean;
  scenarioId: ScenarioPreset["id"] | null;
}

interface InputFormProps {
  values: IntakeFormValues;
  onChange: (values: IntakeFormValues) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  fieldError: FieldError;
  // false when a page-level alert already announces the same message (server validation errors)
  announceFieldError?: boolean;
  presets?: ScenarioPreset[]; // guided demo (#43): fill the text only
  headingRef?: Ref<HTMLHeadingElement>; // focus target for "Start a new intake"
  textRef?: Ref<HTMLTextAreaElement>;
  consentRef?: Ref<HTMLInputElement>;
}

// Announce the counter only near the limit, not on every keystroke
const COUNTER_WARNING_AT = MAX_TEXT_LENGTH - 500;

// Patient-facing intake form. Only patient-provided input lives here; runtime/backend settings do not.
// The page owns the values so a failed submission keeps them and "Start a new intake" can clear them.
export default function InputForm({
  values,
  onChange,
  onSubmit,
  isSubmitting,
  fieldError,
  announceFieldError = true,
  presets = [],
  headingRef,
  textRef,
  consentRef,
}: InputFormProps) {
  const { text, consent, scenarioId } = values;
  const textError = fieldError?.field === "symptoms" ? fieldError.message : null;
  const consentError = fieldError?.field === "consent" ? fieldError.message : null;
  const remaining = MAX_TEXT_LENGTH - text.length;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isSubmitting) onSubmit();
  }

  return (
    <Card as="form" className="intake-form" onSubmit={handleSubmit} noValidate aria-labelledby="intake-form-heading">
      <h2 id="intake-form-heading" ref={headingRef} tabIndex={-1}>
        Tell us what brings you in
      </h2>
      <p className="muted" id="intake-instructions">
        Describe your symptoms in your own words: what you are feeling, when it started, and anything that
        makes it better or worse. Please do not include your name, contact details, date of birth or any
        other identifying information.
      </p>

      {presets.length > 0 && (
        <fieldset className="scenarios" disabled={isSubmitting}>
          <legend className="field-label">Or start from a synthetic scenario</legend>
          <p className="muted small" id="scenario-hint">
            Choosing a scenario fills in the description only. It does not tick consent or send anything.
          </p>
          <ul className="scenario-grid">
            {presets.map((p) => {
              const selected = scenarioId === p.id;
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    className="scenario-card"
                    aria-pressed={selected}
                    aria-describedby="scenario-hint"
                    data-testid={`scenario-${p.id}`}
                    onClick={() => onChange({ ...values, text: p.text, scenarioId: p.id })}
                  >
                    <span className="scenario-name">
                      {p.label}
                      {selected && <span className="scenario-selected">Selected</span>}
                    </span>
                    <span className="scenario-text">“{p.text}”</span>
                    <span className="scenario-expect">
                      <span className="scenario-expect-label">Expected outcome:</span> {p.expect}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </fieldset>
      )}

      <label htmlFor="symptoms" className="field-label">
        Your symptoms <span className="field-required">(required)</span>
      </label>
      <p id="symptoms-hint" className="field-help">
        At least 10 characters. Demo only: please use made-up details, not real personal information.
      </p>
      <textarea
        id="symptoms"
        name="symptoms"
        ref={textRef}
        rows={7}
        value={text}
        maxLength={MAX_TEXT_LENGTH}
        onChange={(e) => {
          const next = e.target.value;
          // Editing away from a scenario's text clears its selected state
          const keep = presets.find((p) => p.id === scenarioId)?.text === next;
          onChange({ ...values, text: next, scenarioId: keep ? scenarioId : null });
        }}
        disabled={isSubmitting}
        aria-required="true"
        aria-invalid={textError ? true : undefined}
        aria-describedby={["symptoms-hint", "symptoms-counter", textError ? "symptoms-error" : null]
          .filter(Boolean)
          .join(" ")}
        placeholder="e.g. I've had a sore throat and a mild fever for two days, and I feel more tired than usual."
      />
      <p id="symptoms-counter" className="field-counter" data-near-limit={remaining <= 500 || undefined}>
        {text.length} / {MAX_TEXT_LENGTH} characters
      </p>
      <p className="visually-hidden" aria-live="polite" data-testid="counter-announcement">
        {text.length >= MAX_TEXT_LENGTH
          ? `Character limit reached: ${MAX_TEXT_LENGTH} characters.`
          : text.length >= COUNTER_WARNING_AT
            ? `${remaining} characters remaining.`
            : ""}
      </p>
      {textError && (
        <p id="symptoms-error" className="inline-error" role={announceFieldError ? "alert" : undefined}>
          {textError}
        </p>
      )}

      <label className="checkbox">
        <input
          type="checkbox"
          ref={consentRef}
          checked={consent}
          onChange={(e) => onChange({ ...values, consent: e.target.checked })}
          disabled={isSubmitting}
          aria-invalid={consentError ? true : undefined}
          aria-describedby={consentError ? "consent-error" : undefined}
        />
        <span>I consent to this information being processed to prepare a summary for my care team.</span>
      </label>
      {consentError && (
        <p id="consent-error" className="inline-error" role={announceFieldError ? "alert" : undefined}>
          {consentError}
        </p>
      )}

      <Button type="submit" variant="primary" disabled={isSubmitting}>
        {isSubmitting ? "Submitting…" : "Submit intake"}
      </Button>
    </Card>
  );
}

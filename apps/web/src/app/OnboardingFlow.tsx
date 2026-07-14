import { useEffect, useId, useRef, useState } from "react";

import {
  WORKSPACE_PREFERENCE_VERSION,
  type ExperienceMode,
  type RuntimeMode,
  type WorkspacePreference,
  type WorkspaceScope
} from "./preferences";

const FINAL_STEP = 3;

interface OnboardingFlowProps {
  onComplete: (preference: WorkspacePreference) => void;
  recovered?: boolean;
}

interface Choice<T extends string> {
  value: T;
  title: string;
  description: string;
}

const EXPERIENCE_CHOICES: readonly Choice<ExperienceMode>[] = [
  {
    value: "everyday",
    title: "Everyday",
    description: "Clear plans, progress, approvals, and results. Technical details stay available."
  },
  {
    value: "developer",
    title: "Developer",
    description: "Repositories, runs, diffs, logs, policy, and precise controls."
  }
];

const SCOPE_CHOICES: readonly Choice<WorkspaceScope>[] = [
  {
    value: "personal",
    title: "Just me",
    description: "Private work and personal automations."
  },
  {
    value: "team",
    title: "My team",
    description: "Assign work, review decisions, and share knowledge."
  }
];

const RUNTIME_CHOICES: readonly Choice<RuntimeMode>[] = [
  {
    value: "local",
    title: "On this computer",
    description: "Corvus and your data stay on this device. Use it in the desktop app or a browser on this computer."
  },
  {
    value: "corvus_cloud",
    title: "Corvus Cloud (E2B)",
    description: "Use the same workspace from desktop and web. Google sign-in required. Cloud Preview; billing comes later."
  }
];

export function OnboardingFlow({ onComplete, recovered = false }: OnboardingFlowProps) {
  const groupName = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [step, setStep] = useState(1);
  const [experience, setExperience] = useState<ExperienceMode | null>(null);
  const [scope, setScope] = useState<WorkspaceScope | null>(null);
  const [runtime, setRuntime] = useState<RuntimeMode | null>(null);

  const heading =
    step === 1
      ? "How do you want Corvus to work with you?"
      : step === 2
        ? "Who is this workspace for?"
        : "Where should Corvus run?";
  const choices =
    step === 1 ? EXPERIENCE_CHOICES : step === 2 ? SCOPE_CHOICES : RUNTIME_CHOICES;
  const selected = step === 1 ? experience : step === 2 ? scope : runtime;

  useEffect(() => {
    headingRef.current?.focus();
  }, [step]);

  function choose(value: string) {
    if (step === 1) setExperience(value as ExperienceMode);
    else if (step === 2) setScope(value as WorkspaceScope);
    else setRuntime(value as RuntimeMode);
  }

  function continueSetup() {
    if (selected === null) return;
    if (step < FINAL_STEP) {
      setStep((current) => current + 1);
      return;
    }
    if (experience === null || scope === null || runtime === null) return;
    onComplete({
      version: WORKSPACE_PREFERENCE_VERSION,
      experience,
      scope,
      runtime,
      onboardingComplete: true
    });
  }

  return (
    <main className="onboarding-shell" id="main-content">
      <section className="onboarding-panel" aria-labelledby="onboarding-heading">
        <div className="onboarding-wordmark" aria-label="Corvus">
          <span aria-hidden="true">C</span>
          <strong>Corvus</strong>
        </div>
        <div className="onboarding-progress">
          <span>Step {step} of {FINAL_STEP}</span>
          <span>Change anytime</span>
        </div>
        {recovered && (
          <p className="setup-notice" role="status">
            Your saved workspace setup could not be read, so we’ll set it up again safely.
          </p>
        )}
        <h1 id="onboarding-heading" ref={headingRef} tabIndex={-1}>{heading}</h1>
        <p className="onboarding-lede">
          {step === 1 && "Choose the level of detail that feels natural. You can always open the deeper view."}
          {step === 2 && "This changes how work is organized, not what you are allowed to access."}
          {step === 3 && "Local is ready now. Cloud is a preview and will never collect payment in this build."}
        </p>
        <fieldset className="choice-grid">
          <legend className="sr-only">{heading}</legend>
          {choices.map((choice) => (
            <label className={`choice-card ${selected === choice.value ? "choice-card--selected" : ""}`} key={choice.value}>
              <input
                checked={selected === choice.value}
                name={`${groupName}-${step}`}
                onChange={() => choose(choice.value)}
                type="radio"
                value={choice.value}
              />
              <span className="choice-card__marker" aria-hidden="true" />
              <span>
                <strong>{choice.title}</strong>
                <small> — {choice.description}</small>
              </span>
            </label>
          ))}
        </fieldset>
        {step === 2 && scope === "team" && (
          <p className="choice-footnote">You can invite people after setup. Selecting Team does not create membership.</p>
        )}
        <div className="onboarding-actions">
          <button className="button button--quiet" disabled={step === 1} onClick={() => setStep((current) => current - 1)} type="button">
            Back
          </button>
          <button className="button button--primary" disabled={selected === null} onClick={continueSetup} type="button">
            {step < FINAL_STEP
              ? "Continue"
              : runtime === "corvus_cloud"
                ? "Continue to Cloud Preview"
                : "Use this computer"}
          </button>
        </div>
      </section>
    </main>
  );
}

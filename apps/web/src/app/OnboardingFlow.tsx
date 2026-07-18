import { useEffect, useId, useRef, useState } from "react";

import type { AuthStatus } from "../auth/AuthProvider";
import type { components } from "../generated/api";
import { BrandLockup } from "../components/Brand";
import type { LegacyPreferenceCandidate } from "./preferences";
import { loadDevicePreferences, saveDevicePreferences, type SafetyGuidance } from "./devicePreferences";

type ExperienceKind = components["schemas"]["ExperienceKind"];
type OnboardingResponse = components["schemas"]["OnboardingResponse"];
type Workspace = components["schemas"]["Workspace"];
type WorkspaceCreate = components["schemas"]["WorkspaceCreate"];
type WorkspaceKind = components["schemas"]["WorkspaceKind"];

type AuthEntryStatus = Extract<AuthStatus, "unauthenticated" | "authenticated">;
type OnboardingStep = "experience" | "workspace" | "safety" | "runtime" | "create";

export interface OnboardingFlowProps {
  accountVersion: number;
  authStatus: AuthEntryStatus;
  experienceKind: ExperienceKind | null;
  onCreateWorkspace(body: WorkspaceCreate, idempotencyKey: string): Promise<Workspace>;
  onExperienceSaved(
    experienceKind: ExperienceKind,
    expectedVersion: number
  ): Promise<OnboardingResponse>;
  onGoogleStart(): void;
  onWorkspaceConfirmed(workspace: Workspace): void | Promise<void>;
  onDismissMigration?(): void;
  preselection?: LegacyPreferenceCandidate | null;
  storage?: Storage;
}

interface Choice<T extends string> {
  description: string;
  title: string;
  value: T;
}

const EXPERIENCE_CHOICES: readonly Choice<ExperienceKind>[] = [
  {
    value: "everyday",
    title: "Everyday",
    description: "Clear plans, progress, approvals, and results with deeper detail available."
  },
  {
    value: "developer",
    title: "Developer",
    description: "Repositories, runs, diffs, logs, policy, and precise controls."
  }
];

const WORKSPACE_CHOICES: readonly Choice<WorkspaceKind>[] = [
  {
    value: "individual",
    title: "Individual",
    description: "Private work and personal automations in an authorized workspace."
  },
  {
    value: "team",
    title: "Team",
    description: "Shared presentation only until real membership is confirmed by Corvus."
  }
];

const SAFETY_CHOICES: readonly Choice<SafetyGuidance>[] = [
  {
    value: "standard",
    title: "Standard guidance",
    description: "Show the active protection and important blocked or confirmed actions."
  },
  {
    value: "detailed",
    title: "Detailed guidance",
    description: "Show more runtime evidence, policy detail, and artifact screening context."
  }
];

const TOTAL_STEPS = 5;

function messageFor(reason: unknown): string {
  if (!(reason instanceof Error)) return "Workspace setup could not be completed. Try again.";
  return reason.message.replaceAll("_", " ");
}

function stepNumber(step: OnboardingStep): number {
  return { experience: 1, workspace: 2, safety: 3, runtime: 4, create: 5 }[step];
}

export function OnboardingFlow({
  accountVersion,
  authStatus,
  experienceKind,
  onCreateWorkspace,
  onExperienceSaved,
  onGoogleStart,
  onWorkspaceConfirmed,
  onDismissMigration,
  preselection = null,
  storage = window.localStorage
}: OnboardingFlowProps) {
  const groupName = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const idempotencyKeyRef = useRef<string | null>(null);
  const [step, setStep] = useState<OnboardingStep>(
    experienceKind === null ? "experience" : "workspace"
  );
  const [experience, setExperience] = useState<ExperienceKind | null>(
    experienceKind ?? preselection?.experience ?? null
  );
  const [workspaceKind, setWorkspaceKind] = useState<WorkspaceKind | null>(
    preselection?.workspaceKind ?? null
  );
  const [runtime, setRuntime] = useState<"local" | null>(
    preselection?.runtimePreselection === "local" ? "local" : null
  );
  const [safetyGuidance, setSafetyGuidance] = useState<SafetyGuidance | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (experienceKind !== null) {
      setExperience(experienceKind);
      setStep((current) => (current === "experience" ? "workspace" : current));
    }
  }, [experienceKind]);

  useEffect(() => {
    headingRef.current?.focus();
  }, [step]);

  useEffect(() => {
    if (error !== null) errorRef.current?.focus();
  }, [error]);

  if (authStatus === "unauthenticated") {
    return (
      <main
        className="onboarding-shell"
        data-corvus-surface="identity-entry"
        data-source-refs="corvus-platform chatgpt-conversion shadcn-button"
        id="main-content"
      >
        <section className="onboarding-panel onboarding-panel--identity" aria-labelledby="identity-heading">
          <BrandLockup className="onboarding-wordmark" />
          <p className="eyebrow">Identity first</p>
          <h1 id="identity-heading">Start with your Corvus identity</h1>
          <p className="onboarding-lede">Use the same governed workspace on your signed-in devices.</p>
          <button
            className="button button--primary onboarding-google"
            data-action="sign-in-google"
            data-component-source="shadcn-button"
            onClick={onGoogleStart}
            type="button"
          >
            Continue with Google
          </button>
        </section>
      </main>
    );
  }

  const heading =
    step === "experience"
      ? "How do you want Corvus to work with you?"
      : step === "workspace"
        ? "Who is this workspace for?"
        : step === "safety"
          ? "How much safety guidance do you want?"
          : step === "runtime"
            ? "Where should Corvus run?"
            : "Name your workspace";

  async function continueExperience() {
    if (experience === null) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await onExperienceSaved(experience, accountVersion);
      setExperience(saved.experience_kind);
      setStep("workspace");
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  async function createWorkspace() {
    if (workspaceKind === null || workspaceName.trim() === "") return;
    if (idempotencyKeyRef.current === null) idempotencyKeyRef.current = crypto.randomUUID();
    setBusy(true);
    setError(null);
    try {
      const workspace = await onCreateWorkspace(
        { name: workspaceName.trim(), workspace_kind: workspaceKind },
        idempotencyKeyRef.current
      );
      const device = loadDevicePreferences(storage, workspace.id);
      saveDevicePreferences(storage, workspace.id, {
        ...device,
        safetyGuidance: safetyGuidance ?? "standard"
      });
      await onWorkspaceConfirmed(workspace);
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  function back() {
    setError(null);
    setStep((current) => {
      if (current === "create") return "runtime";
      if (current === "runtime") return "safety";
      if (current === "safety") return "workspace";
      if (current === "workspace" && experienceKind === null) return "experience";
      return current;
    });
  }

  const canGoBack =
    step === "create" || step === "runtime" || step === "safety" || (step === "workspace" && experienceKind === null);

  return (
    <main
      className="onboarding-shell"
      data-corvus-surface="identity-entry"
      data-source-refs="corvus-platform chatgpt-conversion shadcn-button"
      id="main-content"
    >
      <section className="onboarding-panel" aria-labelledby="onboarding-heading">
        <BrandLockup className="onboarding-wordmark" />
        <div className="onboarding-progress" aria-live="polite">
          <span>Step {stepNumber(step)} of {TOTAL_STEPS}</span>
          <span>Server-backed setup</span>
        </div>
        {error !== null && <div className="setup-error" ref={errorRef} role="alert" tabIndex={-1}>{error}</div>}
        <h1 id="onboarding-heading" ref={headingRef} tabIndex={-1}>{heading}</h1>

        {step === "experience" && (
          <ChoiceGroup<ExperienceKind>
            choices={EXPERIENCE_CHOICES}
            dataChoice="experience"
            groupName={`${groupName}-experience`}
            heading={heading}
            onChoose={setExperience}
            selected={experience}
          />
        )}

        {step === "workspace" && (
          <>
            <p className="onboarding-lede">This changes presentation, not membership or authority.</p>
            <ChoiceGroup<WorkspaceKind>
              choices={WORKSPACE_CHOICES}
              dataChoice="workspace-type"
              groupName={`${groupName}-workspace`}
              heading={heading}
              onChoose={(value) => {
                idempotencyKeyRef.current = null;
                setWorkspaceKind(value);
              }}
              selected={workspaceKind}
            />
          </>
        )}

        {step === "safety" && (
          <>
            <p className="onboarding-lede">This changes how Corvus explains its protection, never the protection itself.</p>
            <ChoiceGroup<SafetyGuidance>
              choices={SAFETY_CHOICES}
              dataChoice="safety-guidance"
              groupName={`${groupName}-safety`}
              heading={heading}
              onChoose={setSafetyGuidance}
              selected={safetyGuidance}
            />
          </>
        )}

        {step === "runtime" && (
          <fieldset className="choice-grid" data-choice="runtime-policy">
            <legend className="sr-only">{heading}</legend>
            <label className={`choice-card ${runtime === "local" ? "choice-card--selected" : ""}`}>
              <input checked={runtime === "local"} name={`${groupName}-runtime`} onChange={() => setRuntime("local")} type="radio" value="local" />
              <span className="choice-card__marker" aria-hidden="true" />
              <span><strong>Local</strong><small> — Available now through your paired local runtime.</small></span>
            </label>
            <label className="choice-card choice-card--disabled">
              <input disabled name={`${groupName}-runtime`} type="radio" value="cloud" />
              <span className="choice-card__marker" aria-hidden="true" />
              <span><strong>Cloud Preview</strong><small> — Preview only. Cloud execution is not available yet.</small></span>
            </label>
            {preselection?.runtimePreselection === "cloud_preview" && (
              <p className="setup-notice" role="status">
                Your previous Cloud choice is preserved as Preview only. Choose Local to continue.
                {onDismissMigration && <button className="text-button" onClick={onDismissMigration} type="button">Dismiss previous setup</button>}
              </p>
            )}
          </fieldset>
        )}

        {step === "create" && (
          <div className="workspace-create-form">
            <label htmlFor="workspace-name">Workspace name</label>
            <input
              id="workspace-name"
              maxLength={200}
              onChange={(event) => {
                if (event.target.value !== workspaceName) idempotencyKeyRef.current = null;
                setWorkspaceName(event.target.value);
              }}
              value={workspaceName}
            />
            <p className="choice-footnote">
              {workspaceKind === "team"
                ? "A Team workspace is created only after this explicit action."
                : "This creates your authorized Individual workspace."}
            </p>
            <div className="onboarding-create-actions">
              <button
                className="button button--primary"
                data-action="create-workspace"
                data-component-source="shadcn-button"
                disabled={busy || workspaceName.trim() === ""}
                onClick={() => void createWorkspace()}
                type="button"
              >
                Create {workspaceKind} workspace
              </button>
              <button
                className="button button--quiet"
                data-action="join-workspace"
                disabled
                title="Workspace invitations are not available yet"
                type="button"
              >
                Join workspace
              </button>
            </div>
          </div>
        )}

        {step !== "create" && (
          <div className="onboarding-actions">
            <button className="button button--quiet" disabled={!canGoBack || busy} onClick={back} type="button">Back</button>
            <button
              className="button button--primary"
              data-component-source="shadcn-button"
              disabled={
                busy ||
                (step === "experience" && experience === null) ||
                (step === "workspace" && workspaceKind === null) ||
                (step === "safety" && safetyGuidance === null) ||
                (step === "runtime" && runtime === null)
              }
              onClick={() => {
                if (step === "experience") void continueExperience();
                else if (step === "workspace") setStep("safety");
                else if (step === "safety") setStep("runtime");
                else setStep("create");
              }}
              type="button"
            >
              Continue
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

function ChoiceGroup<T extends string>({
  choices,
  dataChoice,
  groupName,
  heading,
  onChoose,
  selected
}: {
  choices: readonly Choice<T>[];
  dataChoice: string;
  groupName: string;
  heading: string;
  onChoose(value: T): void;
  selected: T | null;
}) {
  return (
    <fieldset className="choice-grid" data-choice={dataChoice}>
      <legend className="sr-only">{heading}</legend>
      {choices.map((choice) => (
        <label className={`choice-card ${selected === choice.value ? "choice-card--selected" : ""}`} key={choice.value}>
          <input checked={selected === choice.value} name={groupName} onChange={() => onChoose(choice.value)} type="radio" value={choice.value} />
          <span className="choice-card__marker" aria-hidden="true" />
          <span><strong>{choice.title}</strong><small> — {choice.description}</small></span>
        </label>
      ))}
    </fieldset>
  );
}

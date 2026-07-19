import { useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";

import { BrandLockup } from "../components/Brand";
import type { ExperienceMode, WorkspaceKind } from "./preferences";

type Step = "welcome" | "google" | "profile";

export function LocalFirstRunFlow({ onComplete, onGoogleStart = defaultGoogleStart }: {
  onComplete(experience: ExperienceMode, workspaceKind: WorkspaceKind): void;
  onGoogleStart?(): void;
}) {
  const [step, setStep] = useState<Step>("welcome");
  const [googleStarted, setGoogleStarted] = useState(false);
  const [experience, setExperience] = useState<ExperienceMode>("developer");
  const [workspaceKind, setWorkspaceKind] = useState<WorkspaceKind>("individual");

  return <main className="local-first-run" id="main-content"><section className="local-first-run__card">
    <BrandLockup className="onboarding-wordmark" />
    {step === "welcome" ? <>
      <p className="eyebrow">Safety-first agent runtime</p>
      <h1>Welcome to Corvus</h1>
      <p>Corvus helps you plan, build, and contribute with local-first execution, clear permission boundaries, isolated workspaces, and a receipt for every protected run.</p>
      <button className="button button--primary" onClick={() => setStep("google")} type="button">Start setup</button>
    </> : null}
    {step === "google" ? <>
      <p className="eyebrow">Step 1 of 2</p>
      <h1>Connect your identity</h1>
      <p>Sign in with Google in Chrome. Corvus uses your identity for workspace ownership; local project files remain on this device.</p>
      <button className="button button--primary" onClick={() => { onGoogleStart(); setGoogleStarted(true); }} type="button">Continue with Google</button>
      {googleStarted ? <button className="button" onClick={() => setStep("profile")} type="button">I finished signing in · Continue</button> : null}
    </> : null}
    {step === "profile" ? <>
      <p className="eyebrow">Step 2 of 2</p>
      <h1>Make Corvus yours</h1>
      <fieldset><legend>Experience</legend><label><input checked={experience === "everyday"} onChange={() => setExperience("everyday")} type="radio" />Everyday</label><label><input checked={experience === "developer"} onChange={() => setExperience("developer")} type="radio" />Developer</label></fieldset>
      <fieldset><legend>Workspace</legend><label><input checked={workspaceKind === "individual"} onChange={() => setWorkspaceKind("individual")} type="radio" />Individual</label><label><input checked={workspaceKind === "team"} onChange={() => setWorkspaceKind("team")} type="radio" />Team</label></fieldset>
      <button className="button button--primary" onClick={() => onComplete(experience, workspaceKind)} type="button">Open Corvus</button>
    </> : null}
  </section></main>;
}

function defaultGoogleStart(): void {
  const url = "https://corvus-platform-tau.vercel.app/api/v2/auth/google/start?desktop=1";
  if (isTauri()) {
    void invoke("open_external_url", { url });
    return;
  }
  window.open(
    url,
    "_blank",
    "noopener,noreferrer"
  );
}

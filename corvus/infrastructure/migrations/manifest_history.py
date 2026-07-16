from __future__ import annotations

M1_005_FAMILY_NAMES = (
    "access_bundles",
    "agent_grants",
    "audit_anchor_recovery_checkpoints",
    "audit_receipts",
    "audit_result_bindings",
    "audience_policy_snapshots",
    "authority_commit_intents",
    "authority_epoch_credentials",
    "authority_registries",
    "authority_registry_freshness_proofs",
    "authority_registry_trust_states",
    "authority_registry_verifier_keys",
    "authority_state_root_manifests",
    "authority_trust_anchors",
    "authorization_decision_snapshots",
    "capability_grants",
    "delegation_grants",
    "deployment_instance_leases",
    "deployment_instances",
    "idempotency_envelopes",
    "projects",
    "workspace_authorities",
    "workspace_signing_key_versions",
)
M1_006_FAMILY_NAMES = tuple(
    sorted(
        {
            *M1_005_FAMILY_NAMES,
            "authority_close_certificates",
            "authority_handoff_activations",
            "authority_handoffs",
            "restore_validation_receipts",
        }
    )
)
M1_007_FAMILY_NAMES = tuple(
    sorted(
        {
            *M1_006_FAMILY_NAMES,
            "agent_identities",
            "identity_workspaces",
            "principals",
            "scopes",
            "workspace_memberships",
        }
    )
)
M1_008_FAMILY_NAMES = tuple(
    name
    for name in M1_007_FAMILY_NAMES
    if name not in {"audit_anchor_recovery_checkpoints", "audit_result_bindings"}
)


def family_proof_metadata(family_name: str) -> tuple[str, str | None]:
    if family_name == "authority_registry_freshness_proofs":
        return "external_proof", "registry_freshness_proof"
    return "in_root", None

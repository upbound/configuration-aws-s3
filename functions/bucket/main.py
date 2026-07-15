"""Resilience-aware S3 Bucket composition (entry point: ``compose(req, rsp)``).

Composes a single AWS S3 Bucket (``s3.aws.m.upbound.io/v1beta1``) with a
deterministic external-name so every control plane in a resilience set targets
the SAME bucket. The bucket's managementPolicies follow the local
ResilientControlPlane's published decision (the convention contract):

  leader   -> ["*"]        (fully manages the bucket)
  standby  -> ["Observe"]  (observes the same bucket, never mutates)

Fail-safe: when resilience is enabled but no leadership signal is available,
default to ["Observe"] so a bucket is never fought over.
"""

from crossplane.function import resource, response

EXTRA_RESOURCES_KEY = "apiextensions.crossplane.io/extra-resources"


def compose(req, rsp):
    try:
        _compose(req, rsp)
    except Exception as e:
        response.fatal(rsp, f"bucket function error: {e}")


def _resolve_policy(params, req):
    """Return (managementPolicies, reason)."""
    resil = params.get("resilience", {}) or {}
    if not resil.get("enabled", True):
        return ["*"], "resilience disabled -> always manage"

    ctx = resource.struct_to_dict(req.context)
    extra = ctx.get(EXTRA_RESOURCES_KEY, {}) or {}
    rcps = extra.get("resilience", []) or []
    want = resil.get("resilientControlPlaneName")

    chosen = None
    for r in rcps:
        if want is None or r.get("metadata", {}).get("name") == want:
            chosen = r
            break

    policy = None
    if chosen:
        policy = chosen.get("status", {}).get("managementPolicy")
    if policy:
        return policy, "following ResilientControlPlane.status.managementPolicy"
    return ["Observe"], "no leadership signal -> Observe (fail-safe)"


def _compose(req, rsp):
    xr = resource.struct_to_dict(req.observed.composite.resource)
    params = xr.get("spec", {}).get("parameters", {}) or {}
    namespace = xr.get("metadata", {}).get("namespace", "default")

    region = params["region"]
    bucket_name = params["bucketName"]
    provider_config = params.get("providerConfigName", "default")

    mgmt, reason = _resolve_policy(params, req)

    bucket = {
        "apiVersion": "s3.aws.m.upbound.io/v1beta1",
        "kind": "Bucket",
        "metadata": {
            "name": "bucket",
            "namespace": namespace,
            "annotations": {
                "crossplane.io/composition-resource-name": "bucket",
                # Deterministic external-name -> the SAME S3 bucket on every CP.
                "crossplane.io/external-name": bucket_name,
            },
        },
        "spec": {
            "managementPolicies": mgmt,
            "forProvider": {
                "region": region,
                "tags": {"resilient.crossplane.io/managed": "true"},
            },
            "providerConfigRef": {"name": provider_config, "kind": "ProviderConfig"},
        },
    }
    resource.update(rsp.desired.resources["bucket"], bucket)

    rsp.desired.composite.resource.update({"status": {
        "bucketName": bucket_name,
        "managementPolicy": mgmt,
        "reason": reason,
    }})

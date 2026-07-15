"""S3 Bucket composition (entry point: ``compose(req, rsp)``).

Composes a single AWS S3 Bucket (``s3.aws.m.upbound.io/v1beta1``) with a
deterministic ``crossplane.io/external-name`` so every control plane in a
resilience set targets the SAME bucket.

The bucket declares its INTENDED ``managementPolicies``
(``spec.parameters.managementPolicies``, default ``["*"]``). Resilience is
applied by the drop-in ``function-management-policies`` step that follows this
one in the pipeline: on the leader it honors this intent; on a standby it
reduces the bucket to ``["Observe"]``. This function contains no resilience
logic itself.
"""

from crossplane.function import resource, response


def compose(req, rsp):
    try:
        _compose(req, rsp)
    except Exception as e:
        response.fatal(rsp, f"bucket function error: {e}")


def _compose(req, rsp):
    xr = resource.struct_to_dict(req.observed.composite.resource)
    params = xr.get("spec", {}).get("parameters", {}) or {}
    namespace = xr.get("metadata", {}).get("namespace", "default")

    region = params["region"]
    bucket_name = params["bucketName"]
    provider_config = params.get("providerConfigName", "default")
    # Author's intended policy; the resilience overlay honors this on the leader.
    mgmt = params.get("managementPolicies", ["*"])

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

    rsp.desired.composite.resource.update({"status": {"bucketName": bucket_name}})

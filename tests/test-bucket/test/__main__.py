"""Generate the aws-s3 Bucket CompositionTests and print them as YAML.

Offline coverage of the two deterministic resilience branches (the
RCP-following branch is validated in the e2e, since function-extra-resources
cannot inject a ResilientControlPlane offline):
  - resilience enabled, no leadership signal -> ["Observe"] (fail-safe)
  - resilience disabled                      -> ["*"]
Both assert the deterministic external-name (= bucketName) so control planes
share one bucket.
"""

import yaml
from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
from models.io.upbound.dev.meta.compositiontest import v1alpha1 as ct

COMPOSITION = "apis/bucket/composition.yaml"
XRD = "apis/bucket/definition.yaml"
BUCKET_NAME = "resilient-ctp-demo-shared-bucket"


def xr(resilience):
    return {
        "apiVersion": "s3.aws.platform.upbound.io/v1alpha1", "kind": "Bucket",
        "metadata": {"name": "shared-bucket", "namespace": "default"},
        "spec": {"parameters": {
            "region": "us-east-1", "bucketName": BUCKET_NAME,
            "resilience": resilience}},
    }


def assert_bucket(policy):
    return {
        "apiVersion": "s3.aws.m.upbound.io/v1beta1", "kind": "Bucket",
        "metadata": {
            "annotations": {
                "crossplane.io/composition-resource-name": "bucket",
                "crossplane.io/external-name": BUCKET_NAME}},
        "spec": {"managementPolicies": policy,
                 "forProvider": {"region": "us-east-1"},
                 # v2 namespaced MRs require providerConfigRef.kind.
                 "providerConfigRef": {"kind": "ProviderConfig"}},
    }


def test(name, resilience, policy):
    return ct.CompositionTest(
        metadata=k8s.ObjectMeta(name=name),
        spec=ct.Spec(compositionPath=COMPOSITION, xrdPath=XRD, timeoutSeconds=60,
                     validate=True, xr=xr(resilience),
                     assertResources=[assert_bucket(policy)]),
    )


tests = [
    # Enabled but no ResilientControlPlane signal available -> fail-safe Observe.
    test("resilience-default-observe", {"enabled": True}, ["Observe"]),
    # Resilience disabled -> always manage.
    test("resilience-disabled-manage", {"enabled": False}, ["*"]),
]

output = {"items": [t.model_dump(by_alias=True, exclude_none=True) for t in tests]}
print(yaml.dump(output))

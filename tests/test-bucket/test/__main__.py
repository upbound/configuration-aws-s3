"""Generate the aws-s3 Bucket CompositionTest and print it as YAML.

The composition now delegates resilience to function-management-policies (added
late in the pipeline). Offline there is no ResilientControlPlane, so that
function fail-safes and reduces the bucket to ["Observe"]. This test asserts the
bucket is composed with the deterministic external-name and the fail-safe
policy; leader/standby intent-honoring is covered by function-management-policies
itself.
"""

import yaml
from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
from models.io.upbound.dev.meta.compositiontest import v1alpha1 as ct

BUCKET_NAME = "resilient-ctp-demo-shared-bucket"

test = ct.CompositionTest(
    metadata=k8s.ObjectMeta(name="bucket-composed-failsafe"),
    spec=ct.Spec(
        compositionPath="apis/bucket/composition.yaml",
        xrdPath="apis/bucket/definition.yaml",
        timeoutSeconds=60,
        validate=True,
        xr={
            "apiVersion": "s3.aws.platform.upbound.io/v1alpha1",
            "kind": "Bucket",
            "metadata": {"name": "shared", "namespace": "default"},
            "spec": {"parameters": {"region": "us-east-1", "bucketName": BUCKET_NAME}},
        },
        assertResources=[{
            "apiVersion": "s3.aws.m.upbound.io/v1beta1",
            "kind": "Bucket",
            "metadata": {"annotations": {
                "crossplane.io/composition-resource-name": "bucket",
                "crossplane.io/external-name": BUCKET_NAME}},
            "spec": {
                "managementPolicies": ["Observe"],
                "forProvider": {"region": "us-east-1"},
                "providerConfigRef": {"kind": "ProviderConfig"}},
        }],
    ),
)

print(yaml.dump({"items": [test.model_dump(by_alias=True, exclude_none=True)]}))

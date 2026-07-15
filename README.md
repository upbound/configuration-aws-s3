# configuration-aws-s3

A Crossplane v2 configuration that lets a user **claim an S3 `Bucket` in a
region**, implemented with a Python composition function. It is **resilience-aware**
for use with [`configuration-resilient-ctp`](https://github.com/upbound/configuration-resilient-ctp).

## Usage

```yaml
apiVersion: s3.aws.platform.upbound.io/v1alpha1
kind: Bucket
metadata:
  name: shared
  namespace: default
spec:
  parameters:
    region: us-east-1
    # Globally-unique. Use the SAME value on every control plane in a
    # resilience set so they all reference the ONE bucket (via external-name).
    bucketName: my-globally-unique-bucket
    # The bucket's INTENDED managementPolicies. Honored on the resilience
    # leader; reduced to ["Observe"] on standbys. Defaults to ["*"].
    managementPolicies:
      - Create
      - Update
      - Observe
```

## How resilience works

The composition pipeline is:

1. **`bucket`** — composes a single `s3.aws.m.upbound.io` `Bucket` with a
   deterministic `crossplane.io/external-name` (so every control plane targets
   the same bucket) and the **intended** `managementPolicies` above.
2. **[`function-management-policies`](https://github.com/upbound/function-management-policies)**
   (late overlay) — reads the local `ResilientControlPlane`'s leadership and:
   - on the **leader**, leaves the bucket's intended `managementPolicies`
     untouched (so `[Create, Update, Observe]`, `["*"]`, or `["Observe"]` is
     honored — never escalated);
   - on a **standby** (or when no `ResilientControlPlane` is present), reduces the
     bucket to `["Observe"]` — fail-safe.
3. **`function-auto-ready`** — readiness aggregation.

So the leader manages the shared bucket with exactly the policy the claim asked
for, and standbys observe the same bucket. Ownership fails over and back with the
control plane, preserving the intended policy throughout.

## Testing

```bash
up project build
up test run tests/*        # offline composition tests
```

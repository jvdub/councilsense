# ST-012 Deployment and Rollback Runbook

Use this runbook for repeatable staging deployment and rollback across local and AWS runtime paths.

## Scope

- Local runtime deployment and rollback for parity validation.
- AWS staging baseline deployment and rollback for parity validation.

## Local path

### Deploy

1. Start the stack:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

2. Run parity smoke:

```bash
./scripts/local_runtime_smoke.sh
```

3. Record release checklist evidence in `docs/runbooks/st-012-behavior-parity-checklist.md`.

### Rollback

1. Stop current stack:

```bash
docker compose -f docker-compose.local.yml down --remove-orphans
```

2. Rebuild and restart from known-good revision:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

3. Re-run parity smoke:

```bash
./scripts/local_runtime_smoke.sh
```

## AWS staging path

### Deploy (CI entrypoint)

- Preferred: manual dispatch of `.github/workflows/deploy-aws-staging-baseline.yml`.
- Script fallback with explicit environment values:

```bash
STACK_NAME=councilsense-staging-baseline \
ENVIRONMENT_NAME=staging \
IMAGE_IDENTIFIER_API=<account>.dkr.ecr.<region>.amazonaws.com/councilsense-api:<tag> \
IMAGE_IDENTIFIER_WORKER=<account>.dkr.ecr.<region>.amazonaws.com/councilsense-worker:<tag> \
VPC_CONNECTOR_SUBNETS=subnet-aaa,subnet-bbb \
VPC_CONNECTOR_SECURITY_GROUPS=sg-aaa \
DATABASE_SUBNETS=subnet-aaa,subnet-bbb \
DATABASE_SECURITY_GROUPS=sg-bbb \
RDS_MASTER_USER_PASSWORD=<secure-password> \
bash ./scripts/deploy_aws_staging_baseline.sh
```

### Deploy validation

1. Execute `docs/runbooks/st-012-aws-baseline-staging-validation.md` post-deploy checklist.
2. Confirm API health (`/healthz`) and worker running state.
3. Confirm queue/DLQ, storage bucket, and CloudWatch logs are present.
4. Record evidence in `docs/runbooks/st-012-behavior-parity-checklist.md`.

### Rollback

1. Re-run deployment with last known-good image tags:

```bash
STACK_NAME=councilsense-staging-baseline \
ENVIRONMENT_NAME=staging \
IMAGE_IDENTIFIER_API=<known-good-api-tag> \
IMAGE_IDENTIFIER_WORKER=<known-good-worker-tag> \
VPC_CONNECTOR_SUBNETS=<existing-subnets> \
VPC_CONNECTOR_SECURITY_GROUPS=<existing-security-groups> \
DATABASE_SUBNETS=<existing-db-subnets> \
DATABASE_SECURITY_GROUPS=<existing-db-security-groups> \
RDS_MASTER_USER_PASSWORD=<secure-password> \
bash ./scripts/deploy_aws_staging_baseline.sh
```

2. Validate stack status:

```bash
aws cloudformation describe-stacks --stack-name councilsense-staging-baseline
```

3. Re-run the post-deploy smoke checklist and update release evidence.

## Failure handling notes

- If parity checks fail in CI, do not promote deployment artifacts.
- If AWS smoke fails after deploy, rollback to last known-good images first, then triage.
- Any intentional parity deviation requires explicit compensating control in the checklist before release.

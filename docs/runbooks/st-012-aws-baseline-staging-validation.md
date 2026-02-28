# ST-012 AWS Baseline Staging Validation

## Scope

Validate `TASK-ST-012-04` AWS baseline runtime wiring for staging using the shared environment contract.

## Preconditions

- AWS account and region are selected for staging deployment.
- Required network IDs are known (`VPC_CONNECTOR_SUBNETS`, `DATABASE_SUBNETS`, and security groups).
- API and worker container images exist in ECR.
- CI/CD secrets and vars for `.github/workflows/deploy-aws-staging-baseline.yml` are populated.

## Deployment Entry Points

- Manual CI pipeline: `.github/workflows/deploy-aws-staging-baseline.yml`
- Local operator fallback:

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

## Baseline Resource Coverage

Template: `infra/aws/staging-baseline.json`

- Web hosting baseline: SSM pointer `/councilsense/${EnvironmentName}/web/amplify_app_id`
- API runtime: App Runner service `BaselineApiService`
- Worker runtime: App Runner service `BaselineWorkerService`
- Queue + DLQ: `BaselineQueue`, `BaselineDeadLetterQueue`
- Storage: S3 bucket `BaselineArtifactsBucket`
- Database: RDS Postgres `BaselineDatabase`
- Secrets: Secrets Manager `BaselineSessionSecret`, `BaselineDbPasswordSecret`

## Environment Contract Bindings

Both API and worker services bind required startup contract variables:

- `COUNCILSENSE_RUNTIME_ENV=aws`
- `COUNCILSENSE_SECRET_SOURCE=aws-secretsmanager`
- `AUTH_SESSION_SECRET` via Secrets Manager
- `SUPPORTED_CITY_IDS`
- `MANUAL_REVIEW_CONFIDENCE_THRESHOLD`
- `WARN_CONFIDENCE_THRESHOLD`

## ST-011 Telemetry Binding

- `OTEL_EXPORTER_OTLP_ENDPOINT` wired for staging export target.
- `OTEL_RESOURCE_ATTRIBUTES` includes `deployment.environment=aws` and service naming for API/worker.

## Post-Deploy Smoke Checklist

1. `aws cloudformation describe-stacks --stack-name councilsense-staging-baseline`
2. Hit `${ApiServiceUrl}/healthz` and verify HTTP 200.
3. Confirm worker service reaches `RUNNING` in App Runner.
4. Confirm queue and DLQ exist and are writable/readable in SQS console/CLI.
5. Confirm artifacts bucket is present and encrypted.
6. Confirm API/worker logs emit into CloudWatch App Runner log groups.

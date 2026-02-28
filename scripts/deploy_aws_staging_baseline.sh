#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_PATH="${ROOT_DIR}/infra/aws/staging-baseline.json"

STACK_NAME="${STACK_NAME:-councilsense-staging-baseline}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-staging}"

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Template not found: ${TEMPLATE_PATH}" >&2
  exit 1
fi

required_env=(
  IMAGE_IDENTIFIER_API
  IMAGE_IDENTIFIER_WORKER
  VPC_CONNECTOR_SUBNETS
  VPC_CONNECTOR_SECURITY_GROUPS
  DATABASE_SUBNETS
  DATABASE_SECURITY_GROUPS
  RDS_MASTER_USER_PASSWORD
)

for var_name in "${required_env[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    exit 1
  fi
done

aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE_PATH}" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    EnvironmentName="${ENVIRONMENT_NAME}" \
    ImageIdentifierApi="${IMAGE_IDENTIFIER_API}" \
    ImageIdentifierWorker="${IMAGE_IDENTIFIER_WORKER}" \
    VpcConnectorSubnets="${VPC_CONNECTOR_SUBNETS}" \
    VpcConnectorSecurityGroups="${VPC_CONNECTOR_SECURITY_GROUPS}" \
    DatabaseSubnets="${DATABASE_SUBNETS}" \
    DatabaseSecurityGroups="${DATABASE_SECURITY_GROUPS}" \
    RdsMasterUserPassword="${RDS_MASTER_USER_PASSWORD}" \
    RdsMasterUsername="${RDS_MASTER_USERNAME:-councilsense}" \
    CloudWatchLogRetentionDays="${CLOUDWATCH_LOG_RETENTION_DAYS:-14}" \
    ApiCpu="${API_CPU:-0.5 vCPU}" \
    ApiMemory="${API_MEMORY:-1 GB}" \
    WorkerCpu="${WORKER_CPU:-0.5 vCPU}" \
    WorkerMemory="${WORKER_MEMORY:-1 GB}" \
    TelemetryOtlpEndpoint="${TELEMETRY_OTLP_ENDPOINT:-https://otlp.staging.internal:4318}" \
    SupportedCityIds="${SUPPORTED_CITY_IDS:-seattle-wa}" \
  --tags \
    app=councilsense \
    environment="${ENVIRONMENT_NAME}"

echo "Deployed stack ${STACK_NAME} (${ENVIRONMENT_NAME})"

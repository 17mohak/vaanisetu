#!/usr/bin/env bash
# VaaniSetu - provisions all AWS resources with the AWS CLI (region ap-south-1)
set -euo pipefail
export AWS_REGION=ap-south-1 AWS_PAGER=""
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
MEDIA=vaanisetu-media-$ACCOUNT
TABLE=vaanisetu-documents
ROLE=vaanisetu-lambda-role
FN=vaanisetu-api
HERE=$(cd "$(dirname "$0")" && pwd -W)
TMP="$HERE/.build"; mkdir -p "$TMP"

echo "== S3 bucket"
for b in $MEDIA; do
  aws s3api head-bucket --bucket $b 2>/dev/null || aws s3api create-bucket --bucket $b \
    --create-bucket-configuration LocationConstraint=$AWS_REGION >/dev/null
  aws s3api put-public-access-block --bucket $b --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-encryption --bucket $b --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
done
aws s3api put-bucket-cors --bucket $MEDIA --cors-configuration \
  '{"CORSRules":[{"AllowedMethods":["PUT","GET"],"AllowedOrigins":["*"],"AllowedHeaders":["*"],"MaxAgeSeconds":3000}]}'
aws s3api put-bucket-lifecycle-configuration --bucket $MEDIA --lifecycle-configuration \
  '{"Rules":[{"ID":"expire-uploads","Status":"Enabled","Filter":{"Prefix":"uploads/"},"Expiration":{"Days":30}}]}'

echo "== DynamoDB"
if ! aws dynamodb describe-table --table-name $TABLE >/dev/null 2>&1; then
  aws dynamodb create-table --table-name $TABLE --billing-mode PAY_PER_REQUEST \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=createdAt,AttributeType=N \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=createdAt,KeyType=RANGE >/dev/null
  aws dynamodb wait table-exists --table-name $TABLE
fi

echo "== IAM role"
if ! aws iam get-role --role-name $ROLE >/dev/null 2>&1; then
  aws iam create-role --role-name $ROLE --description "VaaniSetu Lambda execution role" \
    --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  sleep 10
fi
aws iam attach-role-policy --role-name $ROLE --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
sed -e "s/__MEDIA__/$MEDIA/g" -e "s/__ACCOUNT__/$ACCOUNT/g" -e "s/__TABLE__/$TABLE/g" \
  "$HERE/lambda-policy.json" > "$TMP/policy.json"
aws iam put-role-policy --role-name $ROLE --policy-name vaanisetu-least-privilege \
  --policy-document "file://$TMP/policy.json"
ROLE_ARN=$(aws iam get-role --role-name $ROLE --query Role.Arn --output text)

echo "== Lambda"
(cd "$HERE/../backend" && python -c "import zipfile;z=zipfile.ZipFile('function.zip','w');z.write('lambda_function.py');z.close()")
ZIP="fileb://$HERE/../backend/function.zip"
ENVV="Variables={MEDIA_BUCKET=$MEDIA,TABLE_NAME=$TABLE,MODEL_ID=global.amazon.nova-2-lite-v1:0}"
if aws lambda get-function --function-name $FN >/dev/null 2>&1; then
  aws lambda update-function-code --function-name $FN --zip-file "$ZIP" >/dev/null
  aws lambda wait function-updated --function-name $FN
  aws lambda update-function-configuration --function-name $FN --environment "$ENVV" >/dev/null
else
  for i in 1 2 3 4 5; do
    aws lambda create-function --function-name $FN --runtime python3.12 \
      --handler lambda_function.lambda_handler --role "$ROLE_ARN" --timeout 29 --memory-size 512 \
      --architectures arm64 --description "VaaniSetu AI document reader API" \
      --environment "$ENVV" --zip-file "$ZIP" >/dev/null && break || sleep 8
  done
fi
aws lambda wait function-active --function-name $FN
aws lambda wait function-updated --function-name $FN
FN_ARN=$(aws lambda get-function --function-name $FN --query Configuration.FunctionArn --output text)

echo "== API Gateway (HTTP API)"
API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='vaanisetu-api'].ApiId" --output text)
if [ -z "$API_ID" ] || [ "$API_ID" = "None" ]; then
  API_ID=$(aws apigatewayv2 create-api --name vaanisetu-api --protocol-type HTTP \
    --cors-configuration 'AllowOrigins=*,AllowMethods=GET,POST,OPTIONS,AllowHeaders=content-type' \
    --query ApiId --output text)
  INT=$(aws apigatewayv2 create-integration --api-id $API_ID --integration-type AWS_PROXY \
    --integration-uri "$FN_ARN" --payload-format-version 2.0 --timeout-in-millis 29000 \
    --query IntegrationId --output text)
  for r in "POST /upload-url" "POST /process" "GET /history"; do
    aws apigatewayv2 create-route --api-id $API_ID --route-key "$r" --target "integrations/$INT" >/dev/null
  done
  aws apigatewayv2 create-stage --api-id $API_ID --stage-name '$default' --auto-deploy \
    --default-route-settings ThrottlingBurstLimit=20,ThrottlingRateLimit=10 >/dev/null
  aws lambda add-permission --function-name $FN --statement-id apigw-invoke \
    --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT:$API_ID/*" >/dev/null
fi
API_URL="https://$API_ID.execute-api.$AWS_REGION.amazonaws.com"
echo "API: $API_URL"

echo "== Frontend -> AWS Amplify Hosting"
sed "s#__API_URL__#$API_URL#" "$HERE/../frontend/config.template.js" > "$HERE/../frontend/config.js"
(cd "$HERE/../frontend" && python -c "
import zipfile, pathlib
with zipfile.ZipFile('../infra/.build/site.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for f in pathlib.Path('.').rglob('*'):
        if f.is_file() and f.name != 'config.template.js':
            z.write(f, f.as_posix())")
APP_ID=$(aws amplify list-apps --query "apps[?name=='vaanisetu'].appId | [0]" --output text)
if [ -z "$APP_ID" ] || [ "$APP_ID" = "None" ]; then
  APP_ID=$(aws amplify create-app --name vaanisetu --platform WEB --query app.appId --output text)
fi
if ! aws amplify get-branch --app-id $APP_ID --branch-name main >/dev/null 2>&1; then
  aws amplify create-branch --app-id $APP_ID --branch-name main --stage PRODUCTION >/dev/null
fi
for j in $(aws amplify list-jobs --app-id $APP_ID --branch-name main \
    --query "jobSummaries[?status=='PENDING'].jobId" --output text); do
  aws amplify stop-job --app-id $APP_ID --branch-name main --job-id $j >/dev/null
done
DEPLOY=$(aws amplify create-deployment --app-id $APP_ID --branch-name main \
  --query '[jobId,zipUploadUrl]' --output text | tr -d '\r')
JOB_ID=$(echo "$DEPLOY" | cut -f1)
UPLOAD_URL=$(echo "$DEPLOY" | cut -f2)
curl -sS --fail-with-body -X PUT -H "Content-Type: application/zip" \
  --data-binary "@$TMP/site.zip" "$UPLOAD_URL"
aws amplify start-deployment --app-id $APP_ID --branch-name main --job-id $JOB_ID >/dev/null
for i in $(seq 1 30); do
  STATUS=$(aws amplify get-job --app-id $APP_ID --branch-name main --job-id $JOB_ID \
    --query job.summary.status --output text | tr -d '\r')
  if [ "$STATUS" = "SUCCEED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
  sleep 4
done
echo "Deployment: $STATUS"
echo "Site: https://main.$(aws amplify get-app --app-id $APP_ID --query app.defaultDomain --output text)"

import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as sns from "aws-cdk-lib/aws-sns";
import * as snsSubs from "aws-cdk-lib/aws-sns-subscriptions";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as path from "path";

/**
 * One Touch Resolve infrastructure.
 *
 * Provisions the serverless backbone that the agent + channel layer run on:
 *   - Two SNS topics for inbound events (EUM SMS/RCS, and EUM Social WhatsApp)
 *   - A Dispatcher Lambda subscribed to both topics (with a DLQ)
 *   - Two DynamoDB tables: claim state (coe-claims) and inbound de-dupe (coe-dedupe, TTL)
 *   - An S3 bucket for inbound media (WhatsApp/RCS attachments)
 *   - Least-privilege IAM allowing the Lambda to send via EUM (sms-voice),
 *     EUM Social (social-messaging), SES, invoke Bedrock AgentCore, and R/W the tables
 *
 * The AgentCore Runtime itself is deployed separately by scripts/deploy_agent.sh
 * (container build + push); its ARN is passed to the Lambda via env var.
 */
export class CoeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ---- DynamoDB: cross-channel claim & party state --------------------
    const claimsTable = new dynamodb.Table(this, "ClaimsTable", {
      tableName: "coe-claims",
      partitionKey: { name: "claim_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // demo convenience
      pointInTimeRecovery: true,
    });

    // Idempotency table for inbound message de-duplication. Entries expire via
    // the `ttl` attribute so the table stays small without manual cleanup.
    const dedupeTable = new dynamodb.Table(this, "DedupeTable", {
      tableName: "coe-dedupe",
      partitionKey: { name: "message_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: "ttl",
    });

    // Managed rental fleet inventory. The agent reserves a real vehicle here
    // (conditional write → no double-booking) when it re-plans a claim with a
    // back-ordered part. Partition key `vehicle_id`.
    const fleetTable = new dynamodb.Table(this, "FleetTable", {
      tableName: "coe-fleet",
      partitionKey: { name: "vehicle_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: true,
    });

    // ---- S3: inbound media (FNOL photos/video) --------------------------
    const mediaBucket = new s3.Bucket(this, "InboundMediaBucket", {
      bucketName: `coe-inbound-media-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [{ expiration: cdk.Duration.days(30) }],
    });

    // ---- SNS: inbound event fan-in --------------------------------------
    const smsRcsInbound = new sns.Topic(this, "SmsRcsInboundTopic", {
      topicName: "coe-eum-sms-rcs-inbound",
      displayName: "EUM SMS/RCS inbound",
    });
    const whatsappInbound = new sns.Topic(this, "WhatsAppInboundTopic", {
      topicName: "coe-eum-social-whatsapp-inbound",
      displayName: "EUM Social WhatsApp inbound",
    });

    // Allow AWS End User Messaging to publish inbound messages to the SNS topic.
    smsRcsInbound.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal("sms-voice.amazonaws.com")],
        actions: ["sns:Publish"],
        resources: [smsRcsInbound.topicArn],
      })
    );
    whatsappInbound.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [
          new iam.ServicePrincipal("social-messaging.amazonaws.com"),
        ],
        actions: ["sns:Publish"],
        resources: [whatsappInbound.topicArn],
      })
    );

    // ---- Dead-letter queue for failed inbound processing ----------------
    const dlq = new sqs.Queue(this, "DispatcherDlq", {
      queueName: "coe-dispatcher-dlq",
      retentionPeriod: cdk.Duration.days(14),
    });

    // ---- Dispatcher Lambda ----------------------------------------------
    const dispatcher = new lambda.Function(this, "DispatcherFn", {
      functionName: "coe-dispatcher",
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "channels.dispatcher.lambda_handler",
      // Package the repo root so `channels`, `agent`, and `shared` are importable.
      // Exclude infra tooling and caches to avoid recursively bundling cdk.out.
      code: lambda.Code.fromAsset(path.join(__dirname, "..", ".."), {
        exclude: [
          "infra",
          "node_modules",
          "cdk.out",
          "dashboard",
          "docs",
          "tests",
          ".git",
          ".sim_output",
          "**/__pycache__",
          "**/*.pyc",
          "*.md",
        ],
      }),
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        SIMULATE_CHANNELS: "false",
        CLAIMS_TABLE_NAME: claimsTable.tableName,
        DEDUPE_TABLE_NAME: dedupeTable.tableName,
        FLEET_TABLE_NAME: fleetTable.tableName,
        INBOUND_MEDIA_BUCKET: mediaBucket.bucketName,
        BEDROCK_MODEL_ID: "amazon.nova-pro-v1:0",
        // Populated post-deploy by scripts/deploy_agent.sh:
        AGENTCORE_RUNTIME_ARN: process.env.AGENTCORE_RUNTIME_ARN || "",
        AGENTCORE_MEMORY_ID: process.env.AGENTCORE_MEMORY_ID || "",
        EUM_ORIGINATION_IDENTITY: process.env.EUM_ORIGINATION_IDENTITY || "",
        WHATSAPP_PHONE_NUMBER_ID: process.env.WHATSAPP_PHONE_NUMBER_ID || "",
        SES_SENDER_EMAIL: process.env.SES_SENDER_EMAIL || "claims@example.com",
      },
      deadLetterQueue: dlq,
    });

    // Subscriptions (with DLQ on the subscription per AWS best practice).
    smsRcsInbound.addSubscription(
      new snsSubs.LambdaSubscription(dispatcher, { deadLetterQueue: dlq })
    );
    whatsappInbound.addSubscription(
      new snsSubs.LambdaSubscription(dispatcher, { deadLetterQueue: dlq })
    );

    // ---- Least-privilege IAM for the dispatcher -------------------------
    claimsTable.grantReadWriteData(dispatcher);
    dedupeTable.grantReadWriteData(dispatcher);
    fleetTable.grantReadWriteData(dispatcher);
    // Inbound FNOL media (WhatsApp/RCS photos & video) is written on receipt and
    // read back by the agent for triage.
    mediaBucket.grantReadWrite(dispatcher);

    dispatcher.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendViaEumSmsRcs",
        effect: iam.Effect.ALLOW,
        actions: ["sms-voice:SendTextMessage", "sms-voice:SendMediaMessage"],
        resources: ["*"],
      })
    );
    dispatcher.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendViaEumSocialWhatsApp",
        effect: iam.Effect.ALLOW,
        actions: ["social-messaging:SendWhatsAppMessage"],
        resources: ["*"],
      })
    );
    dispatcher.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendViaSes",
        effect: iam.Effect.ALLOW,
        actions: ["ses:SendEmail", "ses:SendRawEmail"],
        resources: ["*"],
      })
    );
    dispatcher.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "InvokeAgentCore",
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock-agentcore:InvokeAgentRuntime",
          "bedrock:InvokeModel",
        ],
        resources: ["*"],
      })
    );

    // ---- Observability: alarms on inbound processing -------------------
    // Any message landing in the DLQ means an inbound event failed to process.
    new cloudwatch.Alarm(this, "DlqNotEmptyAlarm", {
      alarmName: "coe-dispatcher-dlq-not-empty",
      alarmDescription: "Inbound messages failed processing and landed in the DLQ.",
      metric: dlq.metricApproximateNumberOfMessagesVisible({
        period: cdk.Duration.minutes(1),
        statistic: "Maximum",
      }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator:
        cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Sustained dispatcher errors indicate a code/permission problem.
    new cloudwatch.Alarm(this, "DispatcherErrorsAlarm", {
      alarmName: "coe-dispatcher-errors",
      alarmDescription: "The dispatcher Lambda is throwing errors.",
      metric: dispatcher.metricErrors({
        period: cdk.Duration.minutes(5),
        statistic: "Sum",
      }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator:
        cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // ---- Outputs --------------------------------------------------------
    new cdk.CfnOutput(this, "SmsRcsInboundTopicArn", {
      value: smsRcsInbound.topicArn,
      description:
        "Point your EUM RCS Agent two-way messaging destination at this topic.",
    });
    new cdk.CfnOutput(this, "WhatsAppInboundTopicArn", {
      value: whatsappInbound.topicArn,
      description: "Point your EUM Social WhatsApp inbound events at this topic.",
    });
    new cdk.CfnOutput(this, "ClaimsTableName", { value: claimsTable.tableName });
    new cdk.CfnOutput(this, "FleetTableName", { value: fleetTable.tableName });
    new cdk.CfnOutput(this, "InboundMediaBucketName", {
      value: mediaBucket.bucketName,
    });
    new cdk.CfnOutput(this, "DispatcherFunctionName", {
      value: dispatcher.functionName,
    });
  }
}

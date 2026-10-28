#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { CoeStack } from "../lib/coe-stack";

const app = new cdk.App();

new CoeStack(app, "CoordinatedOutcomeEngine", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || "us-east-1",
  },
  description:
    "One Touch Resolve — Insurance Claims Coordination Agent " +
    "(AWS CDS Agentic AI Partner Hackathon). SNS + Dispatcher Lambda + " +
    "DynamoDB + IAM for EUM SMS/RCS, EUM Social WhatsApp, and SES.",
});

app.synth();

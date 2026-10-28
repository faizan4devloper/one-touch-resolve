# Prerequisites & Channel Setup

This guide covers the AWS account prerequisites and per-channel setup for the One Touch Resolve.
You can run the **full demo journey in simulation mode with none of the live channel setup** (set
`SIMULATE_CHANNELS=true`). Live channels are only needed for a production/real-device demo.

---

## 0. Account-level prerequisites

- An AWS account with permissions for: Bedrock AgentCore, Lambda, SNS, DynamoDB, SES, S3, IAM, and
  AWS End User Messaging (`sms-voice`) + End User Messaging Social (`social-messaging`).
- AWS CLI v2 configured (`aws configure`).
- Node.js 18+ and the AWS CDK v2 (`npm i -g aws-cdk`).
- Python 3.11+ and Docker (for packaging the AgentCore agent container).
- **Amazon Bedrock model access** enabled for `amazon.nova-pro-v1:0` in your Region.

### Hackathon-specific
- APN registration (required for eligibility) and an **ACE opportunity** created with campaign code
  **"AWS CDS Agentic AI Hackathon - Sept. 2026"**.
- `$50` AWS credits + a Kiro access code are offered to participants (see hackathon FAQ).

---

## 1. AWS End User Messaging — SMS + RCS (with RCS→SMS fallback)

RCS→SMS automatic fallback has a hard requirement:

> The phone **pool** must contain **both** an **AWS RCS Agent** *and* at least one **dedicated SMS phone
> number or sender ID** valid for the destination country. **Shared routes are NOT supported** for RCS
> fallback — the message fails if there is no dedicated originator.

Steps:
1. **Create an AWS RCS Agent** (EUM console → RCS agents). You can stand up a test agent in minutes.
2. **Request/obtain a dedicated SMS number or sender ID** for your destination country.
3. **Create a phone pool** and add *both* the RCS Agent and the SMS number to the **same pool**.
4. **Enable two-way messaging** on the RCS Agent and point it at an **SNS topic** (created by our CDK
   stack, or bring your own). This delivers inbound RCS/SMS as JSON to SNS.
5. Record these in `.env`:
   - `EUM_PHONE_POOL_ID`, `EUM_RCS_AGENT_ID`, `EUM_ORIGINATION_IDENTITY`, `EUM_INBOUND_SNS_TOPIC_ARN`.

Sending uses the same `SendTextMessage` API for RCS and SMS; we send via the **pool** so fallback is
automatic. See `channels/eum_messaging.py`.

---

## 2. AWS End User Messaging Social — WhatsApp

1. Link a **WhatsApp Business Account** to AWS End User Messaging Social.
2. Note the origination **phone number id** → `WHATSAPP_PHONE_NUMBER_ID`.
3. Configure inbound events to publish to an **SNS topic** → `WHATSAPP_INBOUND_SNS_TOPIC_ARN`.
4. Inbound media (photos/video at FNOL) is stored to S3; the dispatcher reads the S3 pointer.

WhatsApp usage is what makes the submission eligible for the **Meta "Best of WhatsApp" $10,000 prize** —
`docs/SUBMISSION.md` includes the required "how WhatsApp was used" description.

---

## 3. Amazon SES

1. **Verify a sender identity** (domain or email) → `SES_SENDER_EMAIL`.
2. If in the SES sandbox, also verify recipient addresses used in the demo, or request production access.
3. (Optional) Create a **configuration set** for open/bounce tracking → `SES_CONFIGURATION_SET`.

---

## 4. Amazon Bedrock AgentCore

1. Ensure AgentCore is available in your Region and Nova Pro model access is enabled.
2. `./scripts/deploy_agent.sh` packages the Strands supervisor + sub-agents, pushes the container, and
   creates the AgentCore Runtime + Memory resources. It writes `AGENTCORE_RUNTIME_ARN` and
   `AGENTCORE_MEMORY_ID` back to `.env`.

---

## 5. Verify

```bash
./scripts/check_prereqs.sh     # validates .env + AWS access for each service
```

Then run the simulated end-to-end journey:

```bash
SIMULATE_CHANNELS=true ./scripts/simulate_demo.sh
```

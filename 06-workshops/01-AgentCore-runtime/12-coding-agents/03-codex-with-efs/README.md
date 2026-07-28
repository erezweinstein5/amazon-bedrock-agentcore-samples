# Codex on AgentCore Runtime with EFS

Deploys the [OpenAI Codex SDK](https://www.npmjs.com/package/@openai/codex-sdk) as an HTTP agent on AWS Bedrock AgentCore Runtime, with an EFS file system mounted at `/mnt/efs` for persistent storage shared across sessions.

Codex runs against models served by Amazon Bedrock through the runtime's IAM execution role. No OpenAI API key is used.

## Architecture

```
  ┌─────────────────────────┐         ┌─────────────────────────┐
  │  AgentCore Runtime      │         │  AgentCore Runtime      │
  │  Session A              │         │  Session B              │
  │  (Codex SDK)            │         │  (Codex SDK)            │
  │                         │         │                         │
  │  /mnt/efs ─────-────────┼────┐    │  /mnt/efs ─────-────────┼────┐
  └─────────────────────────┘    │    └─────────────────────────┘    │
                                 │                                   │
                                 ▼                                   ▼
                    ┌──────────────────────────────────────────────────┐
                    │  EFS File System (encrypted, generalPurpose)     │
                    │                                                  │
                    │  ┌────────────────────────┐                      │
                    │  │  EFS Access Point      │                      │
                    │  │  (uid/gid 1000,        │                      │
                    │  │   root /codex)         │                      │
                    │  └────────────────────────┘                      │
                    │                                                  │
                    │  /mnt/efs/.codex/      CODEX_HOME (threads,       │
                    │                        config.toml, skills)      │
                    │  /mnt/efs/workspace/   git repo Codex edits      │
                    └──────────────────────────────────────────────────┘
```

Multiple runtime sessions mount the same EFS file system, enabling agents to share skills, results, and data across independent invocations.

Because `CODEX_HOME` itself lives on EFS, a **Codex thread** is persistent state, not session state. A thread started in Session A can be resumed from Session B — see Step 3.

```
CloudFormation stack (cfn-vpc.yaml):
  VPC, subnets, NAT Gateway, Security Group
  EFS file system, access point, mount targets

deploy.py creates:
  IAM execution role (Bedrock, ECR, EFS, logs, metrics)
  AgentCore Runtime (container from ECR, EFS mounted at /mnt/efs)
```

## Prerequisites

- Bedrock access to a GPT-5.6 model (default `openai.gpt-5.6-terra`). See [Model availability](#model-availability).
- Docker with buildx (the runtime requires `linux/arm64`)

### Python environment

```bash
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install boto3 awscli --force-reinstall --no-cache-dir
```

## Step-by-step guide

### Step 1 — Infrastructure setup (CloudFormation)

Run the setup script to deploy the CloudFormation stack (VPC, subnets, NAT Gateway, Security Group, EFS), build the arm64 Docker image, and push it to ECR.

```bash
./setup.sh us-west-2
```

All outputs are saved to `envvars.config` and used automatically by the next steps.

### Step 2 — Deploy the agent

Create the IAM execution role and the AgentCore Runtime:

```bash
python deploy.py
```

The script waits until the runtime status is `READY` and saves the runtime config to `runtime_config.json`.

To use a different Bedrock model:

```bash
CODEX_MODEL=openai.gpt-5.6-luna python deploy.py
```

If you need to update an existing runtime (e.g. after rebuilding the Docker image), run:

```bash
python update.py
```

### Step 3 — Invoke the agent

Send a prompt to the deployed agent. The response includes both a `_runtimeSessionId` (the container session) and a `threadId` (the Codex conversation, persisted on EFS).

**Session A** — create a shared skill on the persistent filesystem:

```bash
python invoke.py "can u create a new skill, to review python code? This skill should be created into /mnt/efs/skills/"
```

Continue the conversation within the same session:

```bash
python invoke.py --session <session-a-id> "now add unit tests for that skill"
```

**Session B** — a completely new session accesses the same filesystem and uses the skill created by Session A:

```bash
python invoke.py "list the skills available in /mnt/efs/skills/ and use the python review skill to review this code: def add(a,b): return a+b"
```

Both sessions share `/mnt/efs`, so anything written by one session is immediately available to others.

**Resume a Codex thread from a brand new session.** Because `CODEX_HOME` is on EFS, the conversation itself survives the session that created it:

```bash
python invoke.py --thread <codex-thread-id> "what did we work on earlier?"
```

This is the key difference from session-scoped agents: `--session` resumes the container, `--thread` resumes the conversation.

### Step 4 — Execute a command on the running session

Run a shell command directly on the container using the session ID from the previous step:

```bash
python exec_cmd.py --session <session-id> "ls -l /mnt/efs"
python exec_cmd.py --session <session-id> "ls -l /mnt/efs/.codex/sessions"
```

### Step 5 — Cleanup

Delete all AgentCore resources (runtime, IAM role) and the CloudFormation stack.

```bash
python cleanup.py
```

Or use the shell wrapper:

```bash
./cleanup.sh
```

Deleting the stack deletes the EFS file system and every Codex thread stored on it.

## How Codex is configured for Bedrock

Codex reads its provider configuration from `$CODEX_HOME/config.toml`. `server.js` writes this file on first boot if it is absent:

```toml
model_provider = "amazon-bedrock"
model = "openai.gpt-5.6-terra"
model_reasoning_effort = "medium"
check_for_update_on_startup = false

[model_providers.amazon-bedrock.aws]
region = "us-west-2"
```

Three details matter:

- **Credentials come from the execution role.** `server.js` strips `OPENAI_API_KEY`, `CODEX_API_KEY`, `AWS_BEARER_TOKEN_BEDROCK`, and `AWS_PROFILE` from the environment it hands to Codex, so the container cannot silently fall back to a different identity.
- **The workspace must be a git repository.** Codex refuses to run with `skipGitRepoCheck: false` outside a repo, so `server.js` runs `git init -b main` in `WORKSPACE_DIR` on first boot. This is what gives Codex a diff to reason about.
- **The provider talks to `bedrock-mantle`, which needs extra IAM.** Codex's `amazon-bedrock` provider calls the OpenAI-compatible `bedrock-mantle` endpoint (`https://bedrock-mantle.<region>.api.aws/openai/v1/responses`), not `bedrock-runtime:InvokeModel`. `deploy.py` therefore grants `bedrock-mantle:CreateInference` and `bedrock-mantle:CallWithBearerToken` — equivalent to the `AmazonBedrockMantleInferenceAccess` managed policy.

## Model availability

Because the `amazon-bedrock` provider only reaches the `bedrock-mantle` endpoint, `CODEX_MODEL` must be a **GPT-5.6** model. Other Bedrock model IDs — including `openai.gpt-oss-120b-1:0`, which does appear in `bedrock:ListFoundationModels` — are served by `bedrock-runtime` and return `404 ... does not exist` through Codex.

| `CODEX_MODEL` | `us-east-2` | `us-west-2` |
| --- | --- | --- |
| `openai.gpt-5.6-terra` (default) | yes | yes |
| `openai.gpt-5.6-luna` | yes | yes |
| `openai.gpt-5.6-sol` | yes | no |

Check other regions before overriding the default:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  "https://bedrock-mantle.$REGION.api.aws/openai/v1/responses" \
  -H "Authorization: Bearer $AWS_BEARER_TOKEN_BEDROCK" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$CODEX_MODEL\",\"input\":\"ping\"}"
```

## Request and response format

Request:

```json
{ "prompt": "list the files in the workspace", "threadId": "optional-codex-thread-id" }
```

Response:

```json
{
  "response": "...Codex final response...",
  "threadId": "01JD...",
  "usage": { "input_tokens": 12, "cached_input_tokens": 0, "output_tokens": 34 }
}
```

`usage` includes `cached_input_tokens`, which is where the EFS-persisted thread pays off: resuming a long thread reuses cached prompt tokens instead of re-billing the full history.

## Configuration reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODEX_HOME` | `/mnt/efs/.codex` | Codex state: threads, `config.toml`, skills |
| `WORKSPACE_DIR` | `/mnt/efs/workspace` | Git repo Codex reads and writes |
| `CODEX_MODEL` | `openai.gpt-5.6-terra` | Bedrock model ID (GPT-5.6 family only) |
| `CODEX_REASONING_EFFORT` | `medium` | `minimal`, `low`, `medium`, or `high` |
| `BEDROCK_REGION` | runtime region | Region for Bedrock inference |
| `PORT` | `8080` | HTTP listen port |

## Notes for production

This is a tutorial sample. Before production use, consider:

- Codex runs with `approvalPolicy: "never"` and `sandboxMode: "workspace-write"`, so it edits files under `WORKSPACE_DIR` without asking. Scope the access point path accordingly.
- The security group allows all egress and NFS from the whole VPC CIDR. Restrict both.
- There is no concurrency control. Two simultaneous turns against the same thread can interleave writes on EFS; add a lock if you invoke concurrently.
- Enable VPC Flow Logs and EFS backups.

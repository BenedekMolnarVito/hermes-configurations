---
name: faa-kyma-helm-deployment
description: "Change the FAA Kyma Helm chart: HPA, replicas, quota gating."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [FAA, kyma, helm, autoscaling, hpa, deployment]
    related_skills: [faa-devcontainer-execution, jira-onboard, faa-data-product-wiring]
---

# FAA Kyma Helm Deployment Changes

How to safely change the Financial Analyst Agent's Kyma deployment via Helm-chart
edits only (autoscaling, replicas, resource requests/limits, destinations, env
gating). The chart lives at `deployment/common/kyma/chart/`; run all Git/render/
verify commands inside the devcontainer (see `faa-devcontainer-execution`).

## Chart shape (orient before editing)

- Every template loops `{{- range $i, $d := .Values.deployments }}` and names
  resources via the `aif-kyma-serving.deploymentFullname` helper
  (`templates/_helpers.tpl`), which renders `<projectName>-<name>` (projectName is
  the release prefix, e.g. `dev-fin-analyst-agent`). So the serving Deployment's
  full name is `<release>-fin-analyst-agent-serving` — target HPAs/refs by that
  helper, never a hand-typed name.
- Two deployments exist: `fin-analyst-agent-serving` (JWT, the scale target) and
  `fin-analyst-agent-mcp` (no-auth, `skip_for_pr_deployment`). Scale/HPA the
  serving one only.
- `values.yaml.jinja` is NOT a plain Helm values file: CI renders it with
  `jinja2-cli` first (`.github/workflows/deployment-kyma.yml`), injecting
  `RELEASE_NAME`, `IMAGE_TAG`, `BASE_ENV` (= dev|int|prod), `HOST_ENV`,
  `VAULT_ENVIRONMENT`, `deployments`, `COMMON_ENV_VARS`, and the boolean
  `PR_DEPLOYMENT`. Gate per-env behavior on these jinja vars, THEN Helm renders
  the result. Two template layers — know which one you are editing.
- Sibling repos on the SAME `aif-kyma-serving` framework already ship patterns
  worth copying: `data-product-gateway` and `firefly-proxy` each have
  `templates/hpa.yaml` driven by a `deployments[].hpa` values block. Lift the
  structure from there rather than inventing it.
- `templates/deployment.yaml` renders TWO `resources:` keys in the serving
  container — the `{{- if $d.resources }}` block AND a hardcoded `default` block
  below it. YAML duplicate-key semantics mean the SECOND (hardcoded) block wins,
  so a per-deployment `kyma.deployments[].resources` override is silently
  ignored despite the comment calling it "Overridable." They currently resolve to
  identical values (100m/500m cpu, 1Gi/2Gi mem) so it's harmless today, but the
  HPA baseline (`averageUtilization` is % of the CPU REQUEST, not the limit)
  rests on which block applies — if you change serving resources, delete one of
  the duplicate blocks in the same change or the override won't take effect.

## Adding an HPA (the correct FAA shape)

Three chart changes, all Helm-only, no app/Python change:

1. `templates/hpa.yaml` — per-deployment loop gated on `and $d.hpa $d.hpa.enabled`.
   Use `type: ContainerResource` (NOT `type: Resource`) with
   `container: {{ $d.name }}` so the CPU metric is measured on the app container
   alone — a plain `Resource` metric averages across all pod containers
   (app + injected Istio sidecar), and the sidecar's steady low CPU dilutes the
   signal and makes scaling unpredictable. `ContainerResource` needs k8s >= 1.27 +
   metrics-server; if the cluster rejects it or reports `<unknown>` TARGETS, fall
   back to `type: Resource`.
2. `templates/deployment.yaml` — gate the pinned replicas so Helm does NOT set it
   when the HPA is active: `{{- if not ($d.hpa).enabled }} replicas: ... {{- end }}`.
   Otherwise Helm owns `spec.replicas` and every `helm upgrade` resets it to the
   pinned value, fighting the HPA (tug-of-war). When HPA is off (dev/preview/MCP)
   the pin stays and `replicas: 1` renders as before.
3. `values.yaml.jinja` — add the `hpa` block for the serving deployment only,
   gated by env + preview (see next section).
4. Graceful termination (do this when you enable the HPA, even though it is partly
   pre-existing). Autoscaling makes pod churn ROUTINE: every scale-down and every
   rolling upgrade now terminates serving pods. The default
   `terminationGracePeriodSeconds` is 30s with no `preStop` hook, so a terminating
   pod gets SIGTERM -> 30s -> SIGKILL mid-request. FAA agent requests run ~45–70s,
   so default churn kills in-flight work. Set `terminationGracePeriodSeconds` to >=
   p99 request duration (~90–120s) and add a `preStop` sleep so the pod stops
   taking new work but drains in-flight requests before SIGTERM. Pairs with the
   conservative 300s scaleDown window.
5. minReplicas floor — set it for redundancy, and MEASURE Ready time before
   justifying it as pre-warm. The serving `startupProbe` allows up to ~5 min to go
   Ready (`failureThreshold: 30 x periodSeconds: 10`), but that is a safety CEILING,
   not the typical time. Do NOT raise `minReplicas` as a pre-warm hedge against the
   5-min ceiling without measuring: FAA's real int Ready time is ~70s (check
   `kubectl get events` / pod scheduled->Ready timestamps), far under the ceiling,
   so reactive scale-up is NOT meaningfully startup-delayed and a pre-warm floor is
   unjustified. Set `minReplicas: 2` for single-failure redundancy (serving ran on
   1 replica pre-HPA); under load a failed pod is replaced in ~70s while the HPA
   scales toward `maxReplicas` — the CEILING is the real recovery valve, not the
   floor. Raise the floor above 2 only if measured startup is genuinely slow
   (minutes) or concurrent load grows. A review will (correctly) reject a floor of 3
   justified solely by the 5-min ceiling once Ready time is measured.

Choosing the HPA metric(s) — VERIFY the workload profile first, do not assume.
The tempting default is CPU-only (sticky agent memory from caches/model state does
not fall when load drops, so a memory metric can block scale-down or thrash; keep
the memory LIMIT as the OOM guardrail). But CPU-only is correct ONLY if the app
container's CPU actually rises under load. Confirm against live `kubectl top pod`
+ the pod's request/limit BEFORE committing to CPU-only: if the agent sits CPU-idle
at rest (e.g. ~14m against a 100m request) while memory already exceeds its request
and climbs toward the limit, a CPU-only HPA stays pinned at minReplicas and never
scales under the exact peak load it exists for — it is inert, not conservative. For
that profile add a second `ContainerResource` memory metric at `averageUtilization:
80` (matching the sibling `data-product-gateway` HPA, which scales on both
cpu:70%/memory:80%), and lean on a long `scaleDown` stabilization window (300s) to
blunt the sticky-memory thrash. Do not present the memory omission as a settled
design fact in comments/docs when the live telemetry says the workload is
memory-bound; a reviewer with prod `kubectl` access will (correctly) overturn it.

## maxReplicas is quota-bound — READ the live quota, do not assume it

The ResourceQuota is a PER-CLUSTER object that lives in the namespace, NOT in this
repo — so any quota number written in the chart/docs/plan is an ASSUMPTION until
confirmed against the live int/prod cluster. The repo historically documented an
S-profile `limits.cpu = 4` / `limits.memory = 8Gi`; treat that as a starting guess,
not ground truth. Two things vary by cluster and MUST be read live before computing
maxReplicas:
  - WHICH dimension the quota enforces: `requests.cpu`/`requests.memory` vs
    `limits.cpu`/`limits.memory`. These give wildly different ceilings — a pod
    requesting 150m cpu but limited to 500m counts as 150m against a `requests`
    quota and 500m against a `limits` quota. Getting the dimension wrong (e.g.
    assuming 4-core `limits` when prod actually enforces 8-core `requests`)
    produces a maxReplicas off by several pods.
  - The actual quota SIZE, which can differ dev vs int vs prod (each is a different
    cluster/subaccount).
Read it with `kubectl get resourcequota -n fin-analyst-agent -o yaml` on int AND
prod. If you have no int/prod kubeconfig (the dev devcontext does not grant it),
say so and defer the maxReplicas decision to someone who does — or accept a
reviewer's live reading as authoritative over the repo's documented assumption.

The namespace name is identical in dev/int/prod, but each landscape is a DIFFERENT
GitHub Environment -> different kubeconfig -> different subaccount/cluster.
PR-preview deploys ALWAYS load `deployment/dev/config.conf` and deploy to the DEV
cluster only (CI runs them with `environment: dev`; verify in
`.github/scripts/load_config.py` -> `config_path = ./deployment/{environment}/config.conf`).
So previews contend for the DEV quota, never int/prod. Since the HPA is gated to
int/prod only (see Environment gating), the autoscaler and the PR previews live in
DIFFERENT clusters and never compete for the same quota.

Compute maxReplicas against the CONFIRMED dimension: `maxReplicas x per-pod-cost`
must fit under the live quota with headroom for the MCP pod and an in-flight
upgrade surge pod, where per-pod-cost is the SUM of the app + capped Istio sidecar
along the ENFORCED dimension (requests OR limits, whichever the quota uses). A
maxReplicas the quota cannot admit is UNREACHABLE and fails CLOSED: when the HPA
requests a pod the quota rejects, the ResourceQuota admission controller emits a
`FailedCreate: exceeded quota` event on the ReplicaSet — the pod never schedules,
the HPA stays pinned below target under exactly the peak load it was meant to
handle, and neighbouring deploys/upgrades in the same namespace can also be starved
of quota. Blast radius is namespace-wide.

Scaling past the quota-bound ceiling requires RAISING THE NAMESPACE QUOTA (an
infra/ops request to the Kyma/BTP landscape team), NOT bumping `maxReplicas` alone.
But a quota raise is a CEILING-RAISER, NOT a prerequisite for enabling the HPA:
pick a maxReplicas that fits the confirmed quota today. Record the reasoning in an
inline comment in the `hpa` values block (the confirmed quota dimension + size, the
per-pod cost, what fits, why previews don't contend). The user's standing
preference for FAA is a self-contained comment, NOT a Jira quota-raise ticket. Do
not write `maxReplicas` comments that call the quota raise a blocking prerequisite
or reference a ticket key.

KEEP THE THREE SOURCES IN SYNC: `maxReplicas` appears in `values.yaml.jinja`, the
`hpa.yaml` `default`, the doc (`docs/fin-analyst-agent-hpa.md`), and any
implementation-plan doc. A review will flag any disagreement among them as a
ship-blocking doc/impl mismatch — when you change the ceiling, change ALL of them
in the same edit, and fix the quota rationale text in each (not just the number).

## Environment + preview gating

User preference for FAA autoscaling: HPA runs in `int` and `prod` only — NOT dev,
NOT PR previews (both share the tightest quota and do not need autoscaling; int/
prod are where real concurrent load lands). Gate the `hpa` values block on the
jinja render vars:

    {% if deployment.name.endswith('-serving')
          and BASE_ENV in ['int', 'prod'] and not PR_DEPLOYMENT %}
        hpa:
          enabled: true
          minReplicas: 2
          maxReplicas: <computed from the CONFIRMED live quota>   # see "maxReplicas is quota-bound"
          targetCPU: 70
          ...
    {% endif %}

`BASE_ENV in ['int','prod']` already excludes dev AND PR previews (previews render
with `BASE_ENV=dev`); keep `and not PR_DEPLOYMENT` as defense-in-depth. The same
`{{ "false" if PR_DEPLOYMENT else "true" }}` idiom is already used by
`createDestinations` in the chart — follow it. Name-matching on `-serving` is the
low-risk minimal gate; only surface a per-deployment config flag in
`deployment/<env>/github_actions.conf` if the reviewer prefers config-driven.

## Editing the templates (YAML-validator pitfall)

`templates/*.yaml` are Go templates, not standalone YAML — `{{- range ... }}`,
`{{ include ... }}`, duplicate `resources:` keys, etc. The `patch`/`write_file`
tools run a YAML syntax check on `.yaml` files and will REFUSE the write
(`expected the node content, but found '-'` on line 1) because the template is not
valid YAML on its own. Do NOT fight it: for a template edit, apply the change by
writing the file through a path the validator does not gate — a short
`execute_code` block (`open(path,'w').write(...)`) or a terminal heredoc — rather
than `write_file`/`patch`. Markdown docs (`docs/*.md`) and plain JSON vars files
edit fine with the normal tools. Confirm correctness via `helm template` +
`helm lint` afterward (the real syntax check for templates), not the editor's YAML gate.

## Verify renders in the devcontainer (BOTH gated states)

Because the HPA is env-gated, render and assert BOTH the present and absent cases;
asserting only one hides a gating bug. Mirror the CI's own render
(`jinja2-cli` then `helm template`).

`jinja2-cli` is NOT in the project venv — CI pip-installs it ad-hoc, so a bare
`jinja2 ...` fails `command not found` in the devcontainer. Install it into the
venv once, then invoke via `uv run` (the base interpreter has no project deps):

    uv pip install jinja2-cli
    uv run jinja2 deployment/common/kyma/chart/values.yaml.jinja /tmp/vars-int.json \
      -D APIRULE_BASE_URL=x -D JWT_AUDIENCE=x -D JWT_SCOPE=x -D KYMA_DOMAIN=x \
      -o /tmp/values-int.yaml
    helm template <release> deployment/common/kyma/chart -f /tmp/values-int.yaml \
      --namespace fin-analyst-agent > /tmp/rendered-int.yaml

vars file supplies BASE_ENV + PR_DEPLOYMENT + deployments + projectName. Repeat for
`BASE_ENV=dev` and for `PR_DEPLOYMENT=true`.

Assert on the int/prod render: exactly ONE `kind: HorizontalPodAutoscaler` named
`...-serving-hpa`, `scaleTargetRef.name` == the serving fullname,
`metrics[0].type == ContainerResource` with `container == fin-analyst-agent-serving`,
`maxReplicas` == the quota-bound value, and the serving Deployment has NO
`replicas:` field. Assert on the dev AND preview renders: ZERO HPA, and BOTH
deployments carry `replicas: 1`.

Live (post-deploy to int, since dev gets no HPA): `kubectl get hpa -n
fin-analyst-agent` shows a real CPU % in TARGETS (not `<unknown>`); watch the
serving ReplicaSet for `FailedCreate: exceeded quota` under scale-out — if it
appears below the configured max, the live int/prod quota is tighter than assumed
(do NOT assume the dev-measured quota or repo-documented numbers apply to int/prod
unverified), so lower `maxReplicas` and, only if business load genuinely needs
more pods, pursue a quota raise.

## Commit hygiene

- Commit inside the devcontainer with hooks on; LFS is container-only (see
  `faa-devcontainer-execution`). Never `--no-verify`.
- Never stage the LFS-tracked `db/docs/*.pdf` / `tests/data/*.parquet` files that
  show as modified on the host — that is smudge/clean drift
  (`git check-attr filter -- <path>` returns `filter: lfs`), not a real edit.
  Leave them byte-for-byte untouched.

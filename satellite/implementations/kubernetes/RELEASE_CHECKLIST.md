# Kubernetes satellite release checklist

Use a real OpenShift cluster for this checklist. CI's OpenShift preset runs on kind and verifies the security shape, but it does not exercise an OpenShift security context constraint, Route synthesis, or a GPU device plugin.

- [ ] Publish or stage matching Kubernetes satellite, serving, monitoring, and model-server images, plus the chart.
- [ ] Install the chart with `podSecurity.preset=openshift`, `networkPolicy.enabled=true`, and a real public host; retain the rendered NetworkPolicy for the release record.
- [ ] Confirm the OpenShift ingress controller synthesizes a Route from each standard Ingress and that no chart-owned Route exists.
- [ ] Confirm every satellite, serving, monitoring, collector, store, and model container runs as its OpenShift-assigned user; no pod or container pins a user or group in the rendered preset.
- [ ] Enable the installation's GPU settings and deploy a model requesting a GPU. Confirm the pod lands on a GPU node, receives the configured resource, tolerations, selector, and runtime class, and reaches active.
- [ ] Deploy a real supported model with `networkPolicy.enabled=true`; confirm artifact download and environment creation complete without relaxing the policy.
- [ ] Run authenticated inference and confirm the response and event ID, then open the dashboard and confirm the inference appears.
- [ ] Delete the satellite pod while a sidecar has warm authorization and secret caches; confirm inference continues, then confirm the replacement satellite adopts the deployment.
- [ ] Reissue the satellite token and upgrade its Secret. Confirm the satellite, dashboard, and worker restart and the model pod UIDs do not change.
- [ ] Rotate the derivation key. Confirm the satellite, dashboard, and worker restart, every owned model Deployment rolls, and inference recovers with new companion tokens.
- [ ] Undeploy the model and confirm its Deployment, Service, Ingress, and Secret are removed.
- [ ] Upgrade from the previous chart with the satellite Deployment's `Recreate` strategy; confirm only one satellite polls and existing workloads are adopted before new tasks run.
- [ ] Record the assigned-user audit, GPU node and device-plugin versions, model used, chart diff, inference result, dashboard result, rollout observations, and undeploy result in the release ticket.
- [ ] Create and verify the coordinated tags that apply to this release: `satellite/kubernetes/vX.Y.Z`, `satellite/serving/vX.Y.Z`, `satellite/monitoring/vX.Y.Z`, `satellite/model-server/vX.Y.Z`, and `satellite/kubernetes/chart/vX.Y.Z`.

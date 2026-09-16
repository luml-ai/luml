---
slug: how-data-drift-detection-actually-works
title: "How data drift detection actually works"
description: "A practical walk-through of PSI, KS tests, and embedding drift—and how to decide whether an alert deserves action."
authors:
  - name: DataForce Team
tags:
  - machine-learning
  - monitoring
  - data-drift
type: explainer
jira: LM-710
---

A churn model can keep returning perfectly valid probabilities while the world underneath it changes. The pipeline is green, latency is flat, and nobody has labels yet. Still, this month's customers may no longer resemble the customers whose behavior taught the model what churn looks like.

I'll use one fictional system, HarborTel's churn model, to make that problem concrete. We'll choose two comparison windows, work through population stability and a Kolmogorov-Smirnov test, then move customer-support notes into an embedding space. Finally, we'll decide which alerts deserve investigation rather than another dashboard badge.

HarborTel and every number attached to it are a small constructed example, not production evidence. The simplification matters: real churn systems have delayed labels, correlated features, seasonality, and policy changes that a short calculation can't settle.

## Two windows, one claim

HarborTel scores each account for churn before its next billing cycle. Its structured inputs include `tenure_months`, plan tier, recent usage, and support-contact count. A short support note also becomes a vector through a fixed text encoder.

The monitoring job takes a reference window and a current window. The reference might be the training population, a recent period known to be healthy, or the same season last year. The current window contains the accounts being scored now.

**What are we detecting?**

Data drift means the input distribution has changed between those windows. With an input vector `X`, reference distribution `P_ref`, and current distribution `P_cur`, the claim is:

`P_ref(X) != P_cur(X)`

That is not the same claim as concept drift. Concept drift says the relationship between inputs and the outcome changed, so `P_ref(Y | X) != P_cur(Y | X)`. Label shift says the outcome balance itself changed. Those distinctions matter because an input-only monitor cannot observe the conditional relationship without eventual outcomes.

A drift detector therefore answers a deliberately narrow question: are these two samples compatible with the same input distribution? It does not answer whether churn predictions became worse, whether customers are being harmed, or whether retraining will help.

**Which reference wins?**

There is no universally correct reference. If you compare against training data, you learn whether production left the model's original neighborhood. A rolling reference catches sudden changes but can slowly follow a bad process, while a seasonal reference can miss permanent shifts between seasons.

For HarborTel, let's keep a frozen training reference for model risk and compare consecutive billing cycles for operational faults. The two comparisons answer different questions, so we won't collapse them into one score. [TensorFlow Data Validation](https://www.tensorflow.org/tfx/tutorials/data_validation/tfdv_basic) makes a similar distinction between drift across consecutive spans and skew between training and serving data.

We also freeze the cohort definition. Both windows contain one row per account at the same point in the billing cycle, after the same eligibility filters. If the current job suddenly includes suspended accounts, the detector is correctly describing its input, but the useful diagnosis is a pipeline change.

## The sorting room

Let's picture HarborTel's monitoring system as a parcel-sorting room. Yesterday's account cards sit on the reference belt, and today's cards arrive on the current belt. The room has three stations, each preserving different information from those cards.

At the first station, a clerk drops `tenure_months` cards into fixed trays. The clerk compares each tray's share across belts; that is population stability index, or PSI. At the second, another clerk orders every tenure value and slides a ruler along the two cumulative piles; that is the KS statistic.

The third station handles support notes. It replaces each note with coordinates produced by the text encoder, then compares two clouds of coordinates. That is embedding drift. The monitor's incident lead stands at the exit and asks whether any changed parcel affects the churn decision.

**Why keep three stations?**

Each station throws away something. PSI discards order within a bin. KS keeps numeric order but examines one variable at a time. An embedding can retain semantic relationships across a complex object, but its geometry depends on the encoder that produced it.

No station has a direct line to model quality. They are smoke sensors with different sensitivities, not a fire report. We'll keep returning to the sorting room because the discarded information explains most surprises in drift monitoring.

## Population stability by bins

PSI starts by partitioning one feature into bins. For a numeric feature such as tenure, HarborTel could derive bin edges from reference quantiles. For a categorical feature such as plan tier, each category can act as a bin.

The edges must be learned from the reference and reused for the current window. If you recompute quantile bins on both windows, you force roughly equal shares into each set of trays. That hides the change we meant to measure.

For bin `i`, let `r_i` be its reference share and `c_i` its current share. The population stability index is:

`PSI = sum_i ((c_i - r_i) * ln(c_i / r_i))`

The formula weights larger proportional changes more heavily. An [alternative stable formulation](https://github.com/harcel/unstable_populations) adds a sample-size term inside the log ratio to keep the calculation defined for empty bins.

**What does one bin contribute?**

Let's give the tenure clerk three fixed trays. These shares are pencil-and-paper inputs chosen only to expose the arithmetic:

| Tenure group | Reference share `r_i` | Current share `c_i` | PSI contribution |
| --- | ---: | ---: | ---: |
| New | 0.50 | 0.35 | `(-0.15) * ln(0.35 / 0.50) = 0.0535` |
| Established | 0.30 | 0.35 | `0.05 * ln(0.35 / 0.30) = 0.0077` |
| Long-term | 0.20 | 0.30 | `0.10 * ln(0.30 / 0.20) = 0.0405` |

Adding the tray contributions gives:

`PSI = 0.0535 + 0.0077 + 0.0405 = 0.1017`

Every contribution is non-negative here because the difference and log ratio share a sign. The total is zero only when every current share equals its reference share. A larger result means the binned distributions differ more, not that the model lost a corresponding amount of accuracy.

The New tray supplies the largest contribution. That diagnosis is useful: HarborTel can inspect acquisition channels, account filters, or a promotion aimed at new customers. A single total without bin contributions would tell the incident lead less.

**Why not use a universal cutoff?**

Rules such as “PSI above this number is severe” are conventions, not natural laws. Bin count, bin edges, cohort size, and expected variation all change the score. HarborTel should therefore calibrate thresholds on healthy historical windows and against the cost of investigating false alarms.

Empty trays need an explicit policy because `ln(c_i / r_i)` is undefined when either share is zero. Implementations often add a small positive floor or merge sparse bins. That choice is arbitrary rather than mathematically ordained, so we record it with the detector configuration and test how much it moves past scores.

PSI works well when stable, interpretable bins are already meaningful. But the sorting clerk cannot see a shift inside a tray. If most New accounts move from one month of tenure to five months while both values remain in the same bin, that station stays quiet.

## KS tests by steps

The two-sample Kolmogorov-Smirnov test avoids bins for a continuous feature. It builds an empirical cumulative distribution function, or ECDF: at each value `x`, the ECDF is the fraction of observations less than or equal to `x`.

Let `F_ref(x)` and `F_cur(x)` be the two ECDFs. The KS statistic is the greatest vertical gap between them:

`D = sup_x |F_ref(x) - F_cur(x)|`

The supremum means “the largest value over all positions.” [SciPy's two-sample KS documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html) defines the same statistic and returns the observation where that largest gap occurs.

**Where does the gap appear?**

Shrink HarborTel's belts to a toy set of tenure values. The reference cards read `1, 2, 3, 4, 5`, while the current cards read `3, 4, 5, 6, 7`. Again, these are constructed values, not sampled results.

At `x = 2`, two of five reference cards have passed the ruler, while none of the current cards have. So:

`|F_ref(2) - F_cur(2)| = |2/5 - 0/5| = 0.4`

At `x = 3`, three reference cards and one current card have passed:

`|F_ref(3) - F_cur(3)| = |3/5 - 1/5| = 0.4`

The other positions produce gaps no larger than `0.4`, so `D = 0.4`. In the sorting room, the ruler exposes the exact part of the tenure axis where the belts separate most. There are no bin edges to conceal movement.

The statistic is an effect size on the cumulative distributions. A hypothesis test adds a p-value: assuming independent samples came from the same continuous distribution, how surprising would a statistic at least this large be? The [NIST two-sample description](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/ks2samp.htm) lays out that null hypothesis and ECDF comparison directly.

**Is a small p-value enough?**

No. Sample size changes statistical power, so a large window can make a small operational difference statistically detectable. A tiny window can miss a difference that matters. HarborTel records `D`, the p-value, both sample counts, and the location of the maximum gap rather than reducing the result to pass or fail.

Testing many features creates another trap. If you give each feature its own hypothesis test, some small p-values will appear by chance. We can control a family-wise error rate or a false discovery rate, but either correction expresses a product choice about missed alerts versus noisy ones. [SciPy's false-discovery control documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html) describes Benjamini-Hochberg adjustment and its assumptions.

KS also has boundaries. It is designed for one-dimensional continuous distributions; ties and discrete categories require care. And its largest-gap summary may understate several smaller changes spread across the range.

For HarborTel, KS complements PSI on tenure and usage. PSI offers stable, named trays for diagnosis, while KS checks whether those trays hid movement. Neither tells us how multiple features moved together.

## From fields to embeddings

HarborTel's support note is not one ordered number. A note about repeated outages may use none of the same words as a note about an unstable connection, yet a useful encoder can place their vectors nearby. An embedding is that fixed-length numeric representation of an object such as text.

The monitor applies the same frozen encoder version to reference and current notes. It then compares the resulting vector distributions. This turns a hard comparison over raw language into a tractable comparison over points, but it does not make the points self-explanatory.

**Why not compare each coordinate?**

We could run a univariate test on every coordinate and correct for multiple testing. That may work, and the empirical study [Failing Loudly](https://arxiv.org/abs/1810.11953) found dimensionality reduction followed by two-sample testing effective across the shifts it examined. But embedding axes usually lack standalone business meaning, and a shift can live in relationships across coordinates.

A centroid comparison is another tempting shortcut. Compute the mean vector for each window, then measure their distance. It is cheap, but two clouds can share a center while their shapes differ: imagine current notes splitting equally toward billing complaints and cancellation requests around the old center.

Maximum mean discrepancy, or MMD, compares distributions through a kernel. A kernel gives a similarity between two vectors; MMD asks whether within-reference and within-current similarities look stronger than cross-window similarities. In compact notation:

`MMD(P_ref, P_cur) = ||mu_ref - mu_cur||_H`

Here `mu_ref` and `mu_cur` are mean representations in the kernel's feature space, and `H` names that space. The original [kernel two-sample test paper](https://jmlr.org/papers/v13/gretton12a.html) gives the formal construction and describes quadratic and linear-time estimators.

**What does the kernel add?**

Return to the sorting room. The embedding clerk no longer uses trays or a straight ruler. Instead, the clerk compares every selected card's neighborhood: do current outage notes remain near reference outage notes, and do cancellation notes form a new dense district?

With a characteristic kernel and adequate data, MMD can detect broad distribution differences. But the kernel and its bandwidth decide what “near” means. A very wide bandwidth can blur local changes; a narrow one can react to small local rearrangements.

This is deliberately simplified. Production implementations estimate MMD from samples and commonly use a permutation procedure or calibrated threshold. [Alibi Detect's MMD documentation](https://docs.seldon.ai/alibi-detect/cd/methods/online/onlinemmddrift) also explains the tradeoff: small windows respond faster to severe drift, while larger windows gain power for slight drift.

**Can the encoder itself drift?**

Yes, and that is a different change. If HarborTel upgrades the text encoder, identical notes may acquire different coordinates. Comparing old reference vectors with new current vectors then mixes semantic drift with representation drift.

We handle that by versioning the encoder with the detector. If you upgrade it, re-embed the frozen reference notes with the new encoder and establish a new baseline. The raw-note retention and privacy policy must permit that operation; otherwise, the old and new detector series should remain separate.

Embedding alerts also need examples for diagnosis. We can retrieve current notes that are far from reference neighborhoods, then let an authorized reviewer inspect redacted text. The MMD value says the clouds differ; it does not name “outage complaints” on its own.

## What an alert proves

At this point all three stations can ring. Suppose HarborTel sees higher PSI for tenure, a significant KS result on usage, and embedding drift in support notes. The combined evidence supports one conclusion: today's scored accounts differ from the chosen reference in several monitored representations.

**Does the model now fail?**

Not necessarily. A model can remain accurate under visible drift if the changed features have little influence or if the learned relationship still holds. Conversely, performance can fall while marginal feature distributions look stable because dependencies between features changed or because `P(Y | X)` changed.

The delay in churn labels creates the practical reason for drift monitoring. Drift is available now, while outcome-based accuracy arrives later. So we treat it as an early investigation signal and join it with model evidence when labels mature.

Three checks turn a distance into a diagnosis:

- **Data validity.** Did schema, units, missingness, eligibility, or feature code change? A miles-to-kilometers bug deserves immediate repair even before a model metric moves.
- **Model exposure.** Did the changed field influence predictions, or did the embedding shift occur near important decision regions? Slice prediction scores and explanations cautiously; neither proves causality.
- **Outcome impact.** When labels arrive, did discrimination, calibration, error cost, or subgroup behavior move? Use the metric tied to the churn intervention, not whichever chart is easiest.

HarborTel also compares affected slices. A global tenure shift caused entirely by a new low-risk prepaid plan may not threaten the postpaid churn model if routing is correct. A smaller shift concentrated in customers offered retention benefits can matter more because decisions and costs concentrate there.

**What if only one sensor rings?**

That is normal. PSI may notice category-share movement that KS cannot accept as a categorical test. KS may find within-bin movement that PSI discarded. Embedding MMD may catch a semantic change absent from structured fields.

Disagreement is diagnostic information, not a vote. The incident lead asks what each station preserved, which cohort changed, and whether a known event explains it. A marketing campaign, price change, encoder rollout, and broken join require different owners and responses.

## An actionable alert policy

A useful alert has a runbook and an owner. “PSI exceeded 0.1” is only a condition; it says nothing about urgency, persistence, or the action someone can take. I prefer a policy that combines evidence rather than pretending one threshold carries the decision.

**When should HarborTel page someone?**

First, page immediately for integrity failures: impossible values, missing required features, schema changes, or a serving transformation that disagrees with training. Those are broken contracts, and waiting for a drift score only delays repair.

For distribution alerts, route an investigation when the change clears four gates:

1. **Magnitude:** the effect statistic exceeds a threshold calibrated on known-good windows, not a copied universal cutoff.
2. **Reliability:** the result survives the chosen multiple-test correction or resampling procedure and has enough observations for the monitored slice.
3. **Persistence:** the shift repeats across enough windows to rule out an accepted transient, unless a single-window spike is costly by design.
4. **Relevance:** the changed feature, cohort, or semantic cluster can plausibly alter predictions, interventions, fairness, or data integrity.

Those gates are not equally strict for every feature. An optional marketing field can tolerate more motion than the tenure feature used to determine an offer. HarborTel should encode that asymmetry in detector ownership and severity, not ask an analyst to rediscover it during every alert.

**What action follows?**

The first response is usually investigation, not retraining. Confirm the pipeline and cohort, locate contributing bins or ECDF gaps, retrieve representative embedding neighbors, and annotate known business events. Then compare score distributions and matured performance on the affected slice.

Retraining becomes reasonable when the shifted population is legitimate, persistent, relevant to the model, and represented by trustworthy labels. Even then, a candidate model needs ordinary validation against the population it will serve. Drift detection does not waive that work.

Sometimes the right response is to change the monitor. A harmless annual cycle may need a seasonal reference; a noisy feature may need different bins; an encoder rollout needs a reset baseline. We document that change so a quieter chart cannot masquerade as a healthier model.

At the sorting-room exit, the incident lead now has more than three bells. The record names the reference, cohort, detector version, effect size, uncertainty rule, affected slice, likely owner, and next check. That context makes the alert reversible and auditable.

## The next investigation

Drift monitoring ends where causal diagnosis begins. HarborTel still has to learn whether customers changed, instrumentation changed, or the relationship behind churn changed; no distribution distance can decide that alone.

The next useful artifact is therefore not another universal threshold. It is a replayable case file that joins each alert to raw-data checks, business events, delayed outcomes, and the decision someone made. Over time, those cases can teach the monitoring system which smoke was worth following.

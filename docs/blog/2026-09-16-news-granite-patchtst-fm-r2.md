---
slug: news-granite-patchtst-fm-r2
title: "The Latest Open-Weights Model Release and What It Changes for Practitioners"
description: "IBM's Granite PatchTST-FM-r2 opens a strong time-series forecaster, but its benchmark lead still needs local validation."
authors:
  - name: DataForce Team
tags:
  - open-weights
  - time-series
  - forecasting
type: news
source_url: "https://huggingface.co/blog/ibm-research/ibm-releases-sota-granite-time-series"
jira: LM-711
---

On September 9, 2026, IBM released Granite Time Series PatchTST-FM-r2, a roughly 385-million-parameter forecasting model whose weights, inference pipeline and benchmark files can all be inspected. The release makes another leaderboard claim, but that is not why it matters most. It packages probabilistic, zero-shot forecasting under permissive licences in a form that practitioners can test without first training a model for each dataset.

IBM's [release notes](https://huggingface.co/blog/ibm-research/ibm-releases-sota-granite-time-series) call PatchTST-FM-r2 the leading permissively licensed model in a filtered slice of the GIFT-Eval leaderboard, while placing it second overall among replicable zero-shot systems. That is a strong result, but it isn't an independent verdict that the model will lead on demand, telemetry, energy or financial series; it is a submitted benchmark result inside an independently maintained evaluation framework.

The distinction is unusually visible. IBM's [model card](https://huggingface.co/ibm-granite/granite-timeseries-patchtst-fm-r2) identifies the system as dual-licensed under Apache 2.0 and OpenMDW 1.0, allowing users to choose either licence, and supplies the model configuration and a direct loading path. Meanwhile, the public GIFT-Eval repository records the entry as zero-shot, without test-data leakage, and with replication code available, so another team has the ingredients needed to audit the claim.

For practitioners, this changes the first experiment rather than the final deployment decision. A team can now place a general pretrained forecaster beside its seasonal baseline and task-specific model without a training run. It can request both a point prediction and an uncertainty range, then decide from its own backtest whether IBM's broader benchmark position transfers to the series that pays the bills.

PatchTST-FM-r2 accepts an observed sequence and predicts later values without fitting specifically to that series, a mode generally called zero-shot forecasting. IBM says the model handles contexts as long as 8,192 time steps and produces 99 quantiles, which describe a distribution of possible outcomes rather than only a single best estimate; a practitioner can select a few of those quantiles to form prediction intervals.

The model inherits the idea of dividing a time series into short patches from the original [PatchTST research](https://arxiv.org/abs/2211.14730), much as a language model groups characters into tokens before processing them. In r2, IBM replaced the earlier plain transformer blocks with 30 conformer-style blocks. Each block combines attention over distant patches with convolution over nearby ones, while adjacent patches overlap by half their width to soften boundaries between successive forecast segments.

Those mechanisms are documented architectural choices, but the release does not establish that each one independently caused the leaderboard improvement. IBM's notes show attention-pattern examples and describe the intended division of labour between convolution and attention; they don't report an ablation that isolates every change, so the defensible conclusion is that the complete r2 recipe performed better, not that one component deserves the credit.

The pretraining account is more detailed than a generic statement that the model saw diverse data. According to IBM, the corpus combines selected data from [GIFT-Eval's separate pretraining collection](https://huggingface.co/datasets/Salesforce/GiftEvalPretrain), synthetic sequences based on KernelSynth, a TSMixup corpus built while excluding the benchmark's evaluation sets, and about 500,000 CauKer sequences of 4,096 steps each.

CauKer itself is a synthetic-data method described in a [2025 paper](https://arxiv.org/pdf/2508.02879), but disclosure of the recipe does not eliminate contamination or domain-shift risk. It does give reviewers named components to inspect, and IBM's explicit exclusion claim for the evaluation datasets is more useful than an unspecified training mixture when a team is deciding whether a public benchmark should influence procurement.

The licences also change the practical comparison. The Apache 2.0 option permits commercial use, modification and redistribution subject to its terms, while OpenMDW 1.0 offers a model-specific alternative; neither forces a practitioner onto IBM's hosted service. Open weights still leave infrastructure, monitoring and legal review with the adopter, but the option to run the same artifact behind a private boundary can matter when historical demand or operational telemetry cannot leave an organisation.

At approximately 385 million parameters, PatchTST-FM-r2 is not a tiny statistical model, yet it sits far below the scale of contemporary general-purpose language models. IBM's [published example](https://huggingface.co/blog/ibm-research/ibm-releases-sota-granite-time-series) loads the checkpoint through the Granite TSFM package, consumes recent observations and returns future quantiles without fine-tuning, although the release provides no universal latency or memory figure from which every deployment can budget hardware.

GIFT-Eval offers a broader test than a handful of familiar electricity or traffic datasets. In their October 2024 [benchmark paper](https://arxiv.org/abs/2410.10393), Taha Aksu and seven co-authors described 23 datasets containing more than 144,000 time series and 177 million data points across seven domains and 10 sampling frequencies, with both single-variable and multivariable tasks.

IBM reports that PatchTST-FM-r2 ranks second on both continuous ranked probability score, or CRPS, and mean absolute scaled error, or MASE, after filtering for zero-shot models with replication code and no test leakage. CRPS measures the quality of an entire predictive distribution, while MASE scales absolute error against a simple baseline; lower values are better for both, and IBM reports geometric means of 0.467 and 0.6846 respectively as of September 8.

The independent part is the benchmark design and the public comparison machinery. The current [GIFT-Eval leaderboard](https://huggingface.co/spaces/Salesforce/GIFT-Eval) is operated by Salesforce's benchmark team, and its repository contains PatchTST-FM-r2's per-dataset result file plus metadata identifying IBM TSFM and Rensselaer Polytechnic Institute as the submitting organisations. The repository's [commit history](https://huggingface.co/spaces/Salesforce/GIFT-Eval/commits/main) shows the result being added, rather than a report that Salesforce obtained the weights and reran every evaluation independently.

That does not make the result meaningless. The accepted [result directory](https://huggingface.co/spaces/Salesforce/GIFT-Eval/tree/main/results/Granite-PatchTST-FM-r2) exposes 97 dataset, frequency and forecast-horizon configurations, and the metadata links replication code while classifying the entry as non-leaking. It means the claim is inspectable and reproducible in principle; until another group publishes a rerun, it remains evidence supplied by people connected to the model, evaluated through an external framework.

The leaderboard also narrows what “top performing” means. IBM's release applies that phrase only to zero-shot, replicable entries without identified leakage that also carry permissive commercial licences, while TimesFM-3 sits ahead in the overall filtered comparison. When pretrained entries that may use training portions of evaluation datasets are admitted, IBM says PatchTST-FM-r2 falls to third on CRPS and fourth on MASE, which is still competitive but no longer a single-axis lead.

GIFT-Eval's own research supplies another warning against treating an aggregate rank as a deployment guarantee. Aksu and colleagues found that model behaviour varied by domain, sampling frequency, forecast length and number of variables, and their qualitative analysis showed foundation models missing periodic peaks or degrading over longer horizons on some series even when aggregate scores looked credible.

For an engineering team, the useful consequence is a more disciplined trial. PatchTST-FM-r2 can be tested first as a frozen baseline, preserving the last portion of each local series as an untouched evaluation window and comparing calibration as well as point error; if its intervals miss too often, a favourable CRPS elsewhere won't repair the operational risk.

The release also makes failure analysis easier because the practitioner can keep the weights and inference path fixed while varying context length, forecast horizon and quantiles. That control may reveal whether the model is consistently useful across product lines or merely strong on highly seasonal segments, and it lets a team compare the zero-shot result with a cheaper seasonal-naive forecast before investing in adaptation.

IBM has therefore lowered the cost of asking whether a general time-series model belongs in a forecasting stack, but it has not removed the work between a benchmark and a production decision. If independent reruns confirm the submitted scores and adopters publish results on less benchmark-like operational data, the release could shift zero-shot forecasting from a research comparison into a routine baseline; until then, its openness makes the claim testable rather than settled.

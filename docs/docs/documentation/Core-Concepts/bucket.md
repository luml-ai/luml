---
sidebar_label: 'Buckets'
sidebar_position: 4
title: Buckets
---

# Buckets
A Bucket is an integrated cloud storage solution that ensures the reliable retention of all user assets, from trained models to associated artifacts. Buckets are connected at the Organization level, creating a unified, secure data space for your team.

LUML employs a Client-Side Data Transfer model to guarantee maximum confidentiality. This means the platform (the LUML backend) never acts as an intermediary for your file transfers. The platform's servers do not upload, cache, or read the contents of your storage during upload or download operations.

All file operations (e.g. uploading a model) occur exclusively between your computer and the cloud storage provider. Since traffic does not pass through LUML servers, the platform technically has no access to your raw data. You interact with your storage directly, using the platform's interface merely as a convenient control panel.

By connecting your own Bucket, you gain full autonomy over resource management and security: your data remains under your complete control and never leaves the perimeter of your trusted network.

<!-- [***Bucket creation guide***](../../guides/bucket.md) -->


---
sidebar_position: 4
---

# Buckets

A Bucket is an integrated cloud storage solution that ensures the reliable retention of all user assets, 
from trained models to associated artifacts. Buckets are connected at the Organization level, creating a unified, **secure data space** for your team.

However, the defining feature of Buckets in LUML is not what they store, but *how* the platform interacts with them.

## Security Architecture: Direct Access
LUML employs a Client-Side Data Transfer model to guarantee maximum confidentiality.
This means the platform (the LUML backend) never acts as an intermediary for your file transfers. 
The platform's servers do not upload, cache, or read the contents of your storage during upload or download operations.

### The interaction process is as follows:

**- Direct Channel**: 
All file operations (uploading a dataset, downloading a model) occur exclusively between your browser (frontend) and the cloud storage provider.

**- No third‑party visibility**: 
Since traffic does not pass through LUML servers, the platform technically has no access to your raw data. 
You interact with your storage directly, using the platform's interface merely as a convenient control panel.

This approach ensures ***the highest level of security***: your data remains under your complete control and never leaves the perimeter of your trusted network.

## Control and Scalability
By connecting your own Bucket, you gain full autonomy over resource management. 
Storage capacity is not limited by the platform—it is restricted solely by your needs and the configuration of your cloud provider. 
This allows you to store an unlimited number of models and versions without artificial constraints imposed by LUML.
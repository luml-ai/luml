---
sidebar_label: 'Organization'
sidebar_position: 1
title: Organization
---

# Organization

An Organization is the primary logical boundary within the LUML platform. It serves as the root context for platform operations and provides a top-level namespace within which resources can be created, governed and utilized. All usage quotas, such as the number of users or [Orbits](./orbit.md), are enforced per Organization, and invited users operate under the limits of the Organization they are currently working in.

Once an Organization is created, you can invite users and assign permissions, create Orbits to run projects, and attach Buckets that serve as shared storage backends for those Orbits. Users access data through the Orbits they work with, while storage remains centrally configured at the Organization level.

In short, the Organization is where you set up who can work with you, what projects they can access, and which shared storage resources support those projects.

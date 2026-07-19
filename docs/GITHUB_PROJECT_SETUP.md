# GitHub Project Setup For MyValidCV

This checklist follows the Kanban tutorial and adapts it to the private
`call07564221643-code/MyValidCV_Clean` repository.

## 1. Link The Project To The Private Repository

Open:

```text
https://github.com/users/call07564221643-code/projects/7/views/2
```

Then:

1. Click the three dots `...` at the top right.
2. Click `Settings`.
3. Find `Default repository`.
4. Select `call07564221643-code/MyValidCV_Clean`.
5. Click `Save changes`.

If the repository does not appear, the Project does not have access to the
private repository. In that case:

1. Open the repository.
2. Go to `Settings`.
3. Go to `Projects`.
4. Link Project 7 to the repository.
5. Return to Project Settings and select it as the default repository.

## 2. Configure Kanban Columns

Use these columns:

- Backlog
- To Do
- In Progress
- In Review
- Done

Optional:

- Blocked

## 3. Create MoSCoW Labels In The Repository

Go to:

```text
Repository -> Issues -> Labels -> New label
```

Create:

| Label | Description | Colour |
| --- | --- | --- |
| Must Have | Critical for MVP | `#FF0000` |
| Should Have | Important but not critical | `#FFA500` |
| Could Have | Nice to have | `#FFFF00` |
| Won't Have | Out of scope for now | `#808080` |
| user story | Agile user story | `#4F46E5` |
| bug | Production defect | `#EF4444` |
| ux | User experience improvement | `#14B8A6` |

## 4. Create Story Points Field

In the Project:

1. Click `...`.
2. Click `Settings`.
3. Click `New field` or `+`.
4. Name: `Story Points`.
5. Type: `Number`.
6. Save.

Use Fibonacci values: `1, 2, 3, 5, 8, 13`.

## 5. Create Sprint Field

In the Project:

1. Click `...`.
2. Click `Settings`.
3. Click `New field` or `+`.
4. Type: `Iteration`.
5. Name: `Sprint`.
6. Duration: `1 week`.
7. Start date: next Monday.
8. Save.

Recommended first sprints:

- Sprint 1: finish MVP review and smoke testing.
- Sprint 2: conversion and report-page improvements.
- Sprint 3: owner reporting, trust content and polish.

## 6. Create MVP Milestone

In the repository:

1. Go to `Issues`.
2. Click `Milestones`.
3. Click `New milestone`.
4. Title: `MVP v1.0`.
5. Description: `Minimum viable MyValidCV SaaS release with landing, authentication, dashboard, CV upload, ATS result, payment and owner control.`
6. Due date: choose your final project submission/demo date.
7. Save.

## 7. Create User Stories As Issues

Use:

```text
Repository -> Issues -> New issue -> User Story
```

Create issues from `docs/KANBAN_BOARD.md` and `docs/PRODUCT_BACKLOG.md`.

Recommended issue set:

- User Story: Validate CV Against Job Role
- User Story: Improve Report Page Copy Hierarchy
- User Story: Complete Stripe Payment Confirmation Review
- User Story: Final UX Smoke Test
- User Story: Prepare Final Review And Presentation
- User Story: Owner Promo Code Workflow
- User Story: Pricing Page Conversion Review
- User Story: First-Time User Onboarding

## 8. Add Issues To Project 7

If automation does not add an issue:

1. Open the issue.
2. In the right sidebar, find `Projects`.
3. Select Project 7.
4. Set `Status`.
5. Set `Story Points`.
6. Set `Sprint`.
7. Set `Milestone`.

## 9. Suggested Board Status Today

Because most MVP coding is complete:

- Done:
  - Landing page
  - Authentication
  - Dashboard
  - Owner control centre
  - CV upload
  - ATS result page
  - Pricing
  - Stripe integration
  - Agile documentation
  - PageSpeed readiness

- In Review:
  - Final UX smoke test
  - Manual PageSpeed score capture
  - Payment end-to-end confirmation

- To Do:
  - Final presentation screenshots
  - Demo script
  - Final README polish

## 10. Important Difference From The Tutorial

Your repository is private. That is fine, but the Project must have permission to
see the private repository. If the repo does not appear in the Project settings,
link Project 7 from the repository settings first.

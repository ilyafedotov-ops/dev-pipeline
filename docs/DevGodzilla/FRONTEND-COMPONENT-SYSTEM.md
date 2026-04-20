# DevGodzilla Frontend Component System

> Status: Active
> Scope: Frontend component taxonomy, ownership boundaries, and extension points
> Source of truth: `frontend/components/`, `frontend/app/`
> Last updated: 2026-04-20

## Summary

The frontend component tree is organized by responsibility rather than by generic design-system layers alone.

Use this map to decide where a new component belongs.

## `components/ui`

Purpose:

- reusable primitives
- visual wrappers
- low-level form, layout, dialog, table, and status components

Examples:

- buttons, inputs, dialogs, cards, tabs
- loading and empty states
- status pills and code blocks

Rule:

- keep backend-specific business logic out of `ui`

## `components/layout`

Purpose:

- app shell
- sidebar, header, breadcrumbs, command palette

These components define navigation structure and global layout, not domain workflows.

## `components/features`

Purpose:

- reusable domain composites that span multiple pages

Examples:

- agent dashboards
- feedback panels
- event/log consoles
- template manager
- specification viewer

Use this directory for reusable feature slices that are too domain-aware for `ui` but not tied to one page.

## `components/agile`

Purpose:

- sprint board
- task modal and task detail tabs
- mobile kanban behavior

This directory owns task and sprint interaction patterns, not protocol execution logic.

## `components/workflow`

Purpose:

- higher-level execution visualization such as pipeline views

Use this for workflow/pipeline-specific rendering that spans protocol or task-cycle views.

## `components/speckit`

Purpose:

- spec workflow-specific UI
- SpecKit-centric status and progression surfaces

Use this directory for components that exist because of the SpecKit lifecycle rather than because of generic execution or project navigation.

## `components/wizards`

Purpose:

- modal or guided entrypoints into major workflows

Current examples:

- project wizard
- generate-specs wizard
- design-solution wizard
- implement-feature wizard
- SpecKit launch dialog

These are workflow entry components, not long-lived workspace views.

## `components/visualizations`

Purpose:

- charts and pipeline visualizations
- metrics-oriented display widgets

Keep display-focused visual components here when they can be reused outside a single page.

## `components/shared`

Purpose:

- small cross-cutting helpers that are not pure primitives but also not domain-heavy

Examples:

- shared error boundaries
- clarification dialog
- wizard skeletons

## Page-Coupled Components

Project and protocol detail pages also have local `components/` folders under `frontend/app/...`.

Use page-local components when:

- the component is tightly coupled to one route
- the API usage is specific to that page
- reuse outside that workspace is unlikely

Promote a page-local component into `components/features/` only when reuse becomes real.

## Extension Guidance

Prefer this order when placing new UI code:

1. page-local component if the surface is route-specific
2. `components/features/` for reusable domain composites
3. `components/ui/` for generic primitives

Avoid putting protocol/project business rules into `components/ui/`, and avoid turning every route-specific component into a global feature component too early.

## Related Docs

- `FRONTEND-ARCHITECTURE.md`
- `FRONTEND-WORKSPACES.md`

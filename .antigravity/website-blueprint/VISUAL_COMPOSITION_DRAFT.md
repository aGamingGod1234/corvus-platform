# Corvus Visual Composition Draft

## Composition thesis

One adaptive field desk holds seven product surfaces. Navigation and identity stay stable; the center changes from conversation to schedule, settings, or collaboration; the contextual plane appears only when selected work needs evidence. The flightpath connects request, execution, approval, and result across those planes.

## Desktop shell

```text
+----------------------+-----------------------------------------+----------------------+
| Corvus               | Workspace / profile       Runtime truth | Contextual inspector |
| New thread           +-----------------------------------------+                      |
| Search               | Thread title + share state              | artifact / approval  |
| Inbox                |                                         | evidence / run detail|
| Schedules            | Conversation and flightpath             |                      |
| workspace routes     |                                         |                      |
|                      |                                         |                      |
| Settings             +-----------------------------------------+                      |
| account              | attach  model runtime autonomy [Send]   |                      |
+----------------------+-----------------------------------------+----------------------+
```

The inspector column is absent when no context is selected. It does not reserve an empty generic panel.

## Tablet shell

```text
+------------------+------------------------------------------------+
| compact rail     | identity / runtime                              |
|                  +------------------------------------------------+
| routes           | primary surface                                |
|                  |                                                |
|                  +------------------------------------------------+
|                  | persistent composer                            |
+------------------+------------------------------------------------+
                                         inspector opens as drawer ->
```

## Mobile shell

```text
+--------------------------------------+
| workspace · profile        runtime   |
| thread title                         |
|                                      |
| conversation / selected surface      |
| flightpath becomes compact timeline  |
|                                      |
| attach  controls...          Send    |
+--------------------------------------+
| New | Search | Inbox | Schedule | More|
+--------------------------------------+
```

The composer remains above the bottom navigation and respects safe-area insets. Inspector, filters, profile details, and More use semantic sheets with focus restoration.

## Seven treatment map

1. Identity entry: centered decision lane with a narrow evidence rail and no dashboard shell.
2. Conversation: open reading plane anchored by the persistent composer.
3. Run flightpath: horizontal route on desktop, vertical/compact route on mobile, extending into evidence.
4. Schedules: time ruler plus calendar/list, not repeated cards.
5. Settings and integrations: indexed settings rail with an editable document plane and health ledger.
6. Team collaboration: assignment lanes and a review queue tied to presence and immutable activity.
7. Runtime continuity: local-to-control-plane-to-cloud topology with explicit readiness and recovery actions.

## Source hooks

Every surface root uses `data-source-refs="..."`. Primary/secondary action implementations adapted from shadcn use `data-component-source="shadcn-button"`. The composer send glyph uses `data-component-source="lucide-send"`. These hooks support audits but do not replace the visible source-influence explanation.

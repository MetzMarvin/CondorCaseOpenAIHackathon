# Condor Care Hub: frontend design guidelines

This guide extracts the design language and interaction patterns of the current demo frontend. Use it when extending the demo or building related screens so that new work feels consistent and keeps the case journey understandable.

It describes a Condor-inspired hackathon mockup, not an official Condor brand standard or a production-ready component library. Values below come from the current source; recommended improvements are identified separately.

## 1. Design intent

The interface makes three questions easy to answer: **What happened to this case? Who owns it now? What happens next?**

- Put the case outcome and next action ahead of technical detail.
- Use yellow to draw attention to the main action, selected case and active workflow step. Keep most surfaces quiet.
- Explain automation with facts, sources and a recorded history. A moving workflow is an explanation of events, not evidence of live processing.
- Keep the same case identity, status and history across presentation and operational views.
- Label synthetic data, simulated delivery and simulated actions where users encounter them.

The three essential journeys are automatic resolution, a request for missing evidence followed by resolution in the same case, and a reasoned handoff for serious or unsupported cases. Missing information and negative sentiment alone must not imply a handoff.

## 2. Two views, one case

### Shared application shell

The white `.topbar` contains the brand, hackathon context and view switcher. The lighter `.controlbar` below it contains the scenario selector and demo actions. These stay outside the presentation canvas.

Keep scenario selection on the left and actions on the right. The yellow primary button starts processing or replays a completed history. Secondary controls include format selection, fullscreen and reset. Reset is a demo-only control and can be hidden with `VITE_DEMO_CONTROLS=false`.

### Presentation view

This view is designed for an audience watching a narrated walkthrough. Preserve the following reading order:

1. Product/team eyebrow and scenario subtitle.
2. Large outcome-oriented headline, paired with the current backend case status.
3. Workflow diagram showing the selected historical event.
4. A dark card explaining what happened and a light card explaining why.
5. Replay controls and a simulation disclosure footer.

The stage uses a warm off-white surface, a yellow/white stripe down the left edge and a restrained shadow. Avoid adding operational forms to this canvas; the service console is the place for detailed work.

### Service console

This view is for inspecting and acting on individual cases:

- **Inbox:** a selectable list showing ID, priority, subject, status, owner and next action.
- **Detail header:** case ID/version, subject, status and ownership/queue.
- **Main column:** messages, prepared handoff when present, facts, sources and attachment links.
- **Action column:** next step, processing/takeover actions, simulated customer reply and attachment upload. Human response controls appear after human takeover.
- **Activity:** the shared event history below the case content.

Use the existing message and action patterns instead of introducing a separate visual language for each scenario.

## 3. Visual palette

These are existing CSS values, grouped by their current purpose. They are not yet CSS custom properties.

| Purpose | Current values | Guideline |
| --- | --- | --- |
| Primary accent | `#ffdc00` | Primary buttons, active workflow node, brand mark, selection stripe. |
| Main text | `#132b40` | Default dark navy text on light surfaces. |
| Strong navy surface | `#142d42` | Selected view tab, explanation card and active node number. Pair with white or yellow. |
| Primary button text | `#122b40` | Dark text on yellow. |
| Application background | `#e6ebef` | Neutral frame around the presentation stage. |
| Presentation background | `#fffef9` | Warm canvas; also used behind diagram captions. |
| Header / controls | `#ffffff` / `#f7f9fa` | White topbar, slightly muted controlbar. |
| Quiet operational surfaces | `#f1f4f6`, `#f2f6f7`, `#eff2f0` | Inbox, outgoing messages and secondary explanation card. |
| Borders | `#d3dce2`, `#dce3e7`, `#e1e7eb` | Thin separation between controls, sections and cards. |
| Keyboard focus | `#287bae` | A 3px outline with 3px offset. |
| Error banner | `#ffe4dc` / `#842d1b` | Error surface/text, separate from business case status. |

Status badges use both a text label and color:

| Status | Visible label in current demo | Background / text |
| --- | --- | --- |
| `NEW` | New | Default badge `#e6edf1`, inherited text |
| `IN_PROGRESS` | In progress | Default badge `#e6edf1`, inherited text |
| `WAITING_FOR_CUSTOMER` | Waiting for customer | `#fff0bf` / `#846000` |
| `WAITING_FOR_SPECIALIST` | With specialists | `#ece3f3` / `#6a4383` |
| `RESOLVED` | Resolved | `#dceee0` / `#286747` |
| `CLOSED` | Closed | Default badge `#e6edf1`, inherited text |

Green means a resolved case or a visited workflow node, depending on context. Purple identifies specialist handling. Do not use the error-banner styling for an ordinary handoff. Keep labels visible so color never carries the meaning alone.

## 4. Typography, spacing and shape

Use the existing system font stack: `Arial, Helvetica, sans-serif`. Case IDs, workflow numbers and replay counters use monospace. No external font download is required.

| Element | Current treatment |
| --- | --- |
| Presentation headline | 44px, weight 750, line-height 1.1, letter-spacing -2px |
| Console case heading | 28px, letter-spacing -0.8px |
| Main explanation heading | 21px, letter-spacing -0.5px |
| Workflow node title | 16px, bold |
| Section headings | 14px in case details; 18px for inbox heading |
| Message body | 13px, line-height 1.6 |
| Explanation body | 12px, line-height 1.6 |
| Eyebrows and metadata | Usually 8–11px, bold/letter-spaced where appropriate |

Preserve hierarchy through size, weight and spacing rather than adding more colors. Tiny metadata is part of the existing presentation design; it is not a recommended minimum size for new operational content.

The stylesheet uses individual pixel values rather than a formal spacing scale. Reuse its common 8, 12, 16, 20, 24 and 30px increments where practical. Typical treatments are:

- Controls: 10px × 14px padding, 7px radius, 1px border.
- Workflow nodes: 14px padding, 10px radius.
- Explanation/message cards: roughly 16–20px padding, 9px radius.
- Console detail area: 30px padding on desktop, 20px on narrow screens.
- Main console columns: 30px gap; explanation cards: 20px gap.

Reserve shadows for the presentation stage, active workflow node and selected inbox item. Most cards rely on borders or a light surface tint.

## 5. Layout and responsive behavior

### Presentation geometry

The stage has a fixed design width of **1280px**. Height follows the selected format:

| Format | Design size |
| --- | --- |
| 16:9 | 1280 × 720 |
| 16:10 | 1280 × 800 |
| 4:3 | 1280 × 960 |

`ResizeObserver` measures the viewport. The app calculates a scale from available width and height, clamps it to 0.1–1.5 and applies `transform: scale(...)` with a top-left origin. The wrapper reserves the scaled width and height. Maintain this relationship when changing the canvas so centering and clipping remain predictable.

The workflow itself is a fixed **1160 × 250px** diagram with absolutely positioned **235 × 78px** nodes and SVG connectors. Changing node size or position also requires updating connector paths and caption placement. This is a small explanatory diagram, not a general graph editor.

### Console geometry

- Desktop: maximum width 1600px; inbox 310px; remaining width for details.
- Detail layout: flexible content column plus a 290px action column.
- At widths up to 1000px: inbox becomes 250px, detail columns stack, controlbar wraps and hackathon metadata is hidden.
- At widths up to 650px: inbox stacks above details with a 280px maximum height and internal scrolling; brand and tabs shrink; detail padding reduces.

The presentation scales as a whole, while the console reflows. Do not apply canvas scaling to forms or use absolute positioning for new console content. Check long subjects, message bodies and translated labels for wrapping.

## 6. Reusable component patterns

| Pattern / source hook | How to extend it |
| --- | --- |
| `Badge`, `.badge.<STATUS>` | Keep the status-to-label mapping centralized. Add a readable label and intentional styling for any new backend status. |
| `.primary`, standard `button` | Emphasize the main action in its area. Use neutral buttons for supporting actions; respect disabled states. |
| `.tabs`, `.selected` | Reuse the navy selected state for the view switcher. |
| `.case-item.active` | Selected case uses pale yellow `#fff8cb`, a yellow inset stripe and a stronger border. |
| `.message`, `.outgoing` | Customer messages are neutral; outgoing messages are indented 25px with a tinted background and yellow left border. Retain the simulated-delivery label. |
| `.handoff` | Use a pale purple panel with reason code, summary, open questions and previous attempts. A handoff needs context, not just an escalation badge. |
| `.explain-main`, `.explain-detail` | Pair a short event explanation with the reason behind it. Keep copy tied to the selected event. |
| `.timeline` | Render backend events in order with sequence/step metadata and a readable summary. |
| `.simulation-note`, `.stage-footer` | Keep simulation disclosures visible near actions and in the presentation. |

The demo currently implements these mostly as JSX sections inside `App`, with only `Badge` and `Flow` as separate components. The patterns above are reuse guidance, not a claim that a standalone component library exists. Extract components when repeated behavior warrants it; no new UI framework is needed for a small addition.

## 7. Interaction and state rules

### Separate replay from authoritative case state

The current case ticket always displays backend state, even when replay is positioned at an earlier event. Preserve the explicit **CURRENT CASE STATUS · BACKEND** and **REPLAY OF RECORDED EVENTS** distinction.

`Flow` reads `events` and the selected event index. Visited nodes use muted green; the current node uses yellow and a pulse. `wait_for_customer` maps visually to the information-request node. Connectors show possible routes, not a dynamically reconstructed execution path.

Replay supports pause/play, previous/next event, scrubbing and three speeds: slow 2600ms, normal 1600ms and fast 800ms per step. Format changes and replay navigation must not submit business commands. Reduced-motion preferences disable CSS animation and transitions; they do not currently disable timed event playback.

### Keep actions consistent with backend ownership

The frontend calls System 1 through `/api`; it does not call models or System 2 directly. Processing, simulated inbound replies and human actions refresh the case list, case detail and event feed from the backend.

- Disable overlapping actions while a command is running; show `Running …` on the demo action.
- Enable AI processing only for an AI-owned case in `NEW` or `IN_PROGRESS`.
- Show human-response controls only for human-owned cases; resolution also requires `IN_PROGRESS` and non-empty reply text.
- Keep case-version and idempotency fields when extending commands. They are part of safe interaction behavior, even though users do not edit them.
- Show request errors in the shared alert banner. The existing retry path retains the original command body for network/server failures; do not generate a fresh idempotency key for that retry.
- Refresh after a `409` conflict so the user sees the backend's current state.
- Do not silently replace API errors with made-up successful outcomes.

See the [shared contracts](subsystems-and-contracts.md) for authoritative subsystem boundaries and data contracts. UI disabling improves feedback; backend validation remains authoritative.

## 8. Content and accessibility

Use short, concrete labels describing the next action or outcome. Avoid exposing raw technical detail as the only explanation. Pair case IDs, owner values, version numbers and reason codes with readable context.

The inspected frontend currently uses English labels; the tables above quote those labels to identify existing elements. Follow the applicable project language instructions when changing copy, and update related labels, explanations and accessibility names together.

Preserve the existing native buttons, selects, range input and textareas, their associated labels, visible keyboard focus, `role="alert"` on errors, and accessible names on icon-only replay buttons. The diagram SVG is decorative (`aria-hidden`); node text and explanation cards convey its meaning.

Recommended improvements for future work, **not guarantees of the current demo**:

- Expose selected view and case state programmatically, for example with `aria-pressed` on the existing switcher buttons or complete tab semantics if adopting a tab pattern.
- Provide a visible label for scenario selection on narrow screens; the existing CSS hides it below 650px.
- Check text contrast, zoom behavior and touch targets, especially tiny presentation metadata after canvas scaling.
- Consider a polite loading/status announcement and an explicit empty-history state.
- Keep replay controllable by keyboard and make reduced-motion behavior clear without assuming that CSS disables playback.

## 9. Developer change checklist

Before handing off a screen or component change:

- Verify that the main action, current owner, current status and next step remain clear.
- Reuse the palette, typography, card treatments and button hierarchy above.
- Check both views, all three aspect ratios and widths around the 1000px and 650px breakpoints.
- Check long content, loading, disabled actions and request errors.
- Walk through clear resolution, missing-information resolution in the same case, and reasoned handoff. Check that an angry but supported case still resolves automatically.
- Confirm replay and formatting controls do not mutate case data, and simulation labels remain visible.
- Check keyboard navigation, focus visibility and reduced-motion behavior.
- Run relevant frontend tests and a build for code changes; record only checks actually performed. Setup and commands are in the [project README](../../README.md).

This guide was extracted from source. It does not record a new browser-based visual or accessibility audit.

## 10. Source map

| Source | What it defines |
| --- | --- |
| [`frontend/src/App.jsx`](../../frontend/src/App.jsx) | Layouts, scenarios, `Badge`, `Flow`, replay, action availability and case state handling. |
| [`frontend/src/style.css`](../../frontend/src/style.css) | Exact colors, typography, geometry, breakpoints, focus and reduced-motion rules. |
| [`frontend/src/api.js`](../../frontend/src/api.js) | API request wrapper, request errors and command key creation. |
| [`frontend/src/App.test.jsx`](../../frontend/src/App.test.jsx) | Existing tests for processing, human ownership and replay without mutations. |
| [`README.md`](../../README.md) | Local startup, demo scenarios and integration limitations. |

When implementation changes, update this guide in the same change so developers can distinguish established patterns from future recommendations.

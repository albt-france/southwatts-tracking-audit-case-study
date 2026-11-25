# Automation ideas with AI agents (each with a human checkpoint)

Ideas for routine tracking work where an AI agent could save time. None is built in this repository; the
checks it would rely on are (validators, monitoring, reconciliation). The rule for all five: the agent
**prepares**, a person **decides**. No agent publishes a container, changes a live campaign or writes to a client
account on its own.

| # | Task | What the agent does | Human checkpoint | Main risk and guard |
|---|---|---|---|---|
| 1 | **UTM link review** | Reads the agency's links file, runs the validator, proposes corrected links with the mapping table, drafts the reply to the agency | Tracking specialist approves the corrections before they are sent | Wrong "correction" of a deliberate value → the agent only proposes values from the mapping table; anything else is flagged, not changed |
| 2 | **Alert triage** | When a monitoring check fails, gathers context (deploy log of the day, related checks, same check on other markets) and writes a first diagnosis with links to the data | On-call person confirms the cause and opens the ticket | Confident but wrong diagnosis → the note lists evidence and alternatives; it never closes an alert |
| 3 | **Container release notes** | Compares two container exports (tags, triggers, variables, consent settings) and drafts the release note and the test list | Author of the change reviews and completes it before publishing | Missed side effect → the diff is attached in full; the note is a summary, not a substitute |
| 4 | **Feed checks** | Runs the feed validator on each new export, groups issues by cause, drafts the message to the feed owner | Feed owner decides what to fix and when | Over-alerting on cosmetic issues → only "disapproval risk" issues are escalated |
| 5 | **Weekly summary** | Writes a one-page summary per market: checks status, expected vs anomalous gaps, open tickets | Tracking specialist edits before it goes to the client | Numbers invented or rounded wrongly → every number comes from the check outputs and is linked to its file |

## Critical view

- Agents are good at **collecting and drafting**; they are weak at knowing what changed outside the data
  (a campaign paused by phone, a promotion). The human checkpoint is where that knowledge comes in.
- Access: read-only on analytics and ad accounts; write access only to a draft folder or a ticket.
- Every agent output keeps a trace (inputs, checks run, version) so it can be audited.
- Measure the gain: time saved per week versus time spent correcting the agent. Stop the ones that do not pay off.

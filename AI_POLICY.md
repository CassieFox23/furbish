# AI policy

AI tools are welcome in furbish. The project is built with them: nearly every commit is authored by Claude, Anthropic's model, working for the maintainer, and some code starts as a draft from a local open-weight model. So this policy isn't about keeping AI out. It's about the person behind each contribution.

## The rules

- **Say what you used.** Name the tool (Claude Code, Cursor, a local model) and what it did, in the pull request or issue. "It drafted the parser, I wrote the tests" is plenty. An `Assisted-by:` line in the commit message is welcome too. Using AI is fine; hiding it isn't, and a pull request that hides it will be closed.
- **Every contribution has a human owner.** An agent can do the work, but never alone: a named person owns all of it. The owner has read the final diff, can explain the change and its edge cases without asking the tool, and has run the tests and the checks in [CONTRIBUTING.md](CONTRIBUTING.md). Whoever opens a pull request is its owner, unless the pull request names another person and that person agrees in it. "The AI wrote it" isn't an answer to a review question. This holds for the maintainer too: Claude's commits here are owned by the maintainer.
- **Only the owner signs.** The owner fills in the "Human owner" part of the pull request template. An agent leaves it for its person and never ticks it on their behalf.
- **Reports come from real runs.** A wrong-flag report or a bug report carries furbish's actual output from your own run. Don't send a write-up of a problem you haven't seen happen. Security reports go through [SECURITY.md](SECURITY.md), checked by a person first.
- **No agent posts on its own.** An issue, pull request or comment an agent writes goes out under its owner's name, checked by them first, every claim included.
- **You can give it.** Opening a pull request means you have the right to submit the change under the GPL-3.0, like the rest of the project.

## For AI agents

An agent working in this repository reads [AGENTS.md](AGENTS.md) first: the layout, the rules every change keeps, and the commands that check it.

## When it goes wrong

A pull request that looks machine-made and unchecked gets a short, friendly note and is closed. Accounts that open them in bulk are blocked.

This policy draws on [REA](https://github.com/morluto/rea/blob/main/CONTRIBUTING.md#pull-request-ownership-and-readiness)'s human owner for every pull request, and the AI policies of [Ghostty](https://github.com/ghostty-org/ghostty/blob/main/AI_POLICY.md) and [attrs](https://github.com/python-attrs/attrs/blob/main/.github/AI_POLICY.md), found through [open-source-ai-contribution-policies](https://github.com/melissawm/open-source-ai-contribution-policies).

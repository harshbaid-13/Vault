# Start here

This folder is a **scaffold**, not the app. There is no code yet. Claude Code writes the code, one stage at a time, following `docs/PLAYBOOK.md`.

## What's in here

```
personal-vault/
├── CLAUDE.md          Project rules. Claude Code reads this automatically every session.
├── START-HERE.md      This file.
├── .gitignore         Keeps secrets and uploaded data out of git.
└── docs/
    ├── SPEC.md        Your original brief.
    ├── PLAYBOOK.md    The 16 stages, each with a ready-made prompt.
    ├── PROGRESS.md    Checklist. Claude ticks items off as it goes.
    └── BACKLOG.md     Parking lot for ideas, so they don't derail a stage.
```

## Setup (once)

1. Copy this folder onto your office computer.
2. Open a terminal inside it and run `git init`, then `git add -A` and `git commit -m "scaffold"`.
3. Start Claude Code in this folder.
4. Before your first stage, open `CLAUDE.md` and check the **Stack** section still matches what you want. Everything after this follows from it.

Stage P0 in the playbook creates the rules file. It's already written for you as `CLAUDE.md`, so **skip P0** and begin at D1.

## The loop

For each stage, send Claude Code exactly this, changing the stage code:

```
Run stage D1 from docs/PLAYBOOK.md. Only this stage.
Stop when its "Done when" checks are ready for me to test.
```

Then:

1. **Test it yourself.** Do the "Done when" checks. From S3 onward, do them on your actual phone.
2. **Verify.** Paste the "Verify a stage" prompt from Part C of the playbook.
3. **Commit.** `git add -A && git commit -m "S4: clipboard"`
4. **Clear.** Type `/clear` to wipe the conversation.
5. **Next stage.** Send the same message with the next code.

Clearing between stages keeps Claude sharp. It loses nothing, because the rules, the plan and the progress file are all on disk.

## Order of stages

Design: D1 → D2 → D3 → D4 → D5
Build: S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10 → S11

Don't skip ahead. S4 sets the code pattern that every later feature copies, and S3 gets the vault onto your phone before there's much to lose.

## Fill in the blanks

The playbook has a few `[square brackets]`. Fill them in before you send those stages:

- **Your office computer's OS** (Windows 11, macOS, or Ubuntu). Appears in D5, S3, S10. It changes the Tailscale, backup and README instructions.
- **Your devices** (iPhone, Android, laptop) in S3.
- **Largest file size** you'll upload, in S6.

## Tips

- Use `/plan` for the design stages and D5. Claude shows its intent before writing anything, which is the cheapest place to catch a bad idea.
- If Claude wants a dependency that isn't in the plan, ask why. `CLAUDE.md` already tells it to check with you.
- S6 (files) and S8 (previews and photos) are the heaviest. If a stage feels too big, split it: "Do the upload half of S6 first, stop, then downloads and serving."
- When something feels over-built, use the "When the code gets too complicated" prompt in Part C.

## After a stage goes wrong

Use the bug report template in Part C. Give it the device and browser, and paste `docker compose logs --tail=50 vault`. Ask for the cause first, then the smallest fix, then a test that would have caught it.

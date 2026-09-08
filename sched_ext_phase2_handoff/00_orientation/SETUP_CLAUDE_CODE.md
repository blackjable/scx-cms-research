# Setting Up Claude Code Itself

Everything else in this bundle is PROJECT content (what to tell Claude
Code once it's running). This file is the one piece that was missing:
how to actually get Claude Code running and pointed at this folder.

You mentioned earlier having Claude Code set up in VS Code already —
if so, skip to **Step 3**. This is here as a complete reference in
case that setup needs redoing, or you switch machines.

## Step 1: Install Claude Code (if not already installed)

As of 2026, Claude Code ships as a native installer — Node.js is no
longer required.

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

This installs the binary to `~/.local/bin/claude` and adds it to your
PATH. Verify it worked:

```bash
claude --version
```

If you get "command not found," your shell didn't pick up the new
PATH entry:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Step 2: Choose CLI or VS Code extension

Claude Code is CLI-first; the VS Code extension is a thin wrapper
around the same underlying engine, adding diff previews and
checkpoint management.

**VS Code extension**: Extensions view (`Cmd+Shift+X`) → search
"Claude Code" → install. Once installed, open any file and click the
orange ✱ (Spark) icon in the editor toolbar, or use the Command
Palette (`Cmd+Shift+P` → "Claude Code").

**Plain CLI**: just run `claude` from any terminal, including VS
Code's integrated terminal.

Either way, first launch opens a browser sign-in flow against your
Claude account (Pro or Max subscription works — no API key needed for
this).

## Step 3: Open this project folder specifically

This is the step that's easy to miss: **Claude Code reads everything
inside whichever folder you open, and nothing outside it.**

1. Unzip `sched_ext_phase2_handoff.zip` somewhere sensible — not a
   Downloads folder you'll lose track of, ideally next to (or inside)
   wherever you'll eventually clone `sched-ext/scx` for real.
2. In VS Code: **File → Open Folder**, select the unzipped
   `sched_ext_phase2_handoff/` folder.
3. Open Claude Code (Spark icon, or `claude` in the integrated
   terminal — either way it now has access to everything in this
   folder).
4. Give it the first prompt suggested in `MANIFEST.md`:

   > "Read 00_orientation/paper_sections_2_to_6_draft.md in full, then
   > 01_delivery_plan/phase2_delivery_plan_update.md. Summarize the
   > current state and the next concrete action per the delivery
   > plan's 'suggested order of operations' section, before writing
   > any code."

## A note on staying current

Claude Code ships updates frequently, and installation specifics can
change. If anything above doesn't match what you see, the canonical
docs are:

- Overview: https://docs.claude.com/en/docs/claude-code/overview
- Docs map: https://docs.anthropic.com/en/docs/claude-code/claude_code_docs_map.md

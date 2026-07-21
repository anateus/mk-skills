# Activation hook

Use this optional hook only when the host repeatedly misses that it is running inside Zellij.

Install the lightweight session-start discovery hook:

```bash
bash "<skill-base-dir>/references/hooks/install-hook.sh"
```

It surfaces Zellij session context; it does not install pane-status, identity, origin, or Hunk lifecycle behavior. Review the installer before running it. Remove only its owned entries with:

```bash
bash "<skill-base-dir>/references/hooks/uninstall-hook.sh"
```

Start a fresh host session and verify that context treats any present `ZELLIJ` value, including `0`, as active.

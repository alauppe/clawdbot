# Plaud.ai CLI Skill

Unofficial CLI for Plaud.ai voice recorder cloud service.

## Location

CLI: `~/clawd/tools/plaud.py` (also symlinked to `/usr/local/bin/plaud`)

## Authentication

Token stored at `~/.config/plaud/token.json`

For OAuth users (Google login), grab token from browser:
1. Log into web.plaud.ai
2. Open DevTools → Console
3. Run: `localStorage.getItem('tokenstr')`
4. Save: `plaud login -t "eyJ..."`

## Commands

### List recordings
```bash
plaud ls                    # List recent recordings
plaud ls --limit 50         # More results
plaud ls --trash            # Show trashed items
plaud ls --json             # Raw JSON output
```

Output columns: `ID (12 chars) | Date | Duration | T:✓/✗ S:✓/✗ | Title`
- T = Transcript available
- S = Summary available

### Recording details
```bash
plaud info <full-id>        # Full recording metadata as JSON
```

### Download recordings
```bash
plaud download <id>                           # Download all (audio + transcript + summary)
plaud download <id> --audio                   # Just MP3
plaud download <id> --transcript              # Just transcript
plaud download <id> --summary                 # Just summary
plaud download <id> --format PDF              # Export as PDF (also: TXT, DOCX, SRT, markdown)
plaud download <id> --outdir ~/recordings     # Specify output directory
```

### Sync all recordings
```bash
plaud sync                              # Sync to ./plaud-recordings/
plaud sync --outdir ~/plaud-archive     # Custom output dir
```

Syncs all recordings, skipping already-downloaded files. Downloads audio + transcript + summary where available.

### Other commands
```bash
plaud me                # Show account info
plaud status            # Check API status
plaud tags              # List folders/tags
plaud share <id>        # Create shareable link
plaud trash <id>...     # Move to trash
plaud untrash <id>...   # Restore from trash
plaud delete <id>...    # Permanently delete (requires confirmation)
```

## Notes

- IDs shown in `ls` are truncated to 12 chars; use `--json` to get full IDs
- Token expires periodically; re-grab from browser localStorage if auth fails
- API is unofficial/reverse-engineered from JamesStuder/Plaud_API

## Examples

```bash
# Get today's recordings
plaud ls --limit 5

# Download latest meeting with transcript
plaud download 0d84544939fbf9daea9c64a6efee28ca --outdir ~/meetings

# Bulk sync everything to archive
plaud sync --outdir ~/Dropbox/plaud-archive

# Export summary as markdown
plaud download abc123... --summary --format markdown
```

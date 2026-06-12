# Draft GitHub issues

One file per issue. Frontmatter gives the target repo and title; the
body below the `---` separator is the issue text. **These are drafts —
do not submit without explicit approval.**

Submit a single issue with:

```bash
gh issue create --repo Mu2e/<repo> --title "<title>" --body-file <(sed '1,/^---$/d; 1,/^---$/d' <file>.md)
```

Or all of them with the helper:

```bash
for f in doc/issues/[0-9]*.md; do
  repo=$(awk -F': ' '/^repo:/{print $2}' "$f")
  title=$(awk -F': ' '/^title:/{sub(/^title: /,""); print}' "$f")
  body=$(awk 'flag>1{print} /^---$/{flag++}' "$f")
  gh issue create --repo "Mu2e/$repo" --title "$title" --body "$body"
done
```

## Naming

- `NN-startstop-<repo>.md` — start/stop script standardization
- `NN-discovery-<repo>.md` — mu2edaq-discovery adoption

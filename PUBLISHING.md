# Publishing to HACS

This guide walks through publishing the ThermoWorks integration to HACS.

## Prerequisites

- [ ] Repository is public on GitHub
- [ ] All code is committed and pushed
- [ ] Tests are passing
- [ ] Documentation is complete

## Pre-Publication Checklist

### 1. Verify Files

Ensure these files exist and are up to date:

- [ ] `README.md` - Complete documentation
- [ ] `info.md` - Short description for HACS UI
- [ ] `hacs.json` - HACS configuration
- [ ] `LICENSE` - MIT license
- [ ] `CHANGELOG.md` - Version history
- [ ] `custom_components/thermoworks_bt/manifest.json` - Version and metadata
- [ ] `.github/workflows/validate.yaml` - CI validation

### 2. Update Version

Before creating a release:

1. Update version in `custom_components/thermoworks_bt/manifest.json`
2. Add entry to `CHANGELOG.md`
3. Commit changes:
   ```bash
   git add custom_components/thermoworks_bt/manifest.json CHANGELOG.md
   git commit -m "Bump version to X.Y.Z"
   git push
   ```

### 3. Create Git Tag

```bash
# Tag the release (use semantic versioning)
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

### 4. Create GitHub Release

1. Go to https://github.com/jamesshannon/thermoworks-ha/releases
2. Click "Create a new release"
3. Select the tag you just created (v0.1.0)
4. Title: "v0.1.0 - Initial Release"
5. Description: Copy from CHANGELOG.md
6. Click "Publish release"

## Submit to HACS

### Option 1: Default Repository (Recommended)

To be included in HACS default repositories:

1. Fork https://github.com/hacs/default
2. Edit `integration` file
3. Add your repository URL:
   ```
   jamesshannon/thermoworks-ha
   ```
4. Create a pull request
5. Wait for HACS team review (can take 1-2 weeks)

### Option 2: Custom Repository (Immediate)

Users can add it immediately as a custom repository:

1. Open HACS in Home Assistant
2. Click the three dots (⋮) in the top right
3. Select "Custom repositories"
4. Add repository URL: `https://github.com/jamesshannon/thermoworks-ha`
5. Category: "Integration"
6. Click "Add"

## Post-Publication

### Update README Badge

Once accepted to HACS default, update the badge in README.md:

```markdown
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
```

### Monitor Issues

- Watch GitHub issues for user reports
- Respond to HACS integration PR feedback
- Keep CHANGELOG.md updated for future releases

## Future Releases

For subsequent releases:

1. Make your changes
2. Update version in `manifest.json`
3. Update `CHANGELOG.md`
4. Commit and push
5. Create new tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
6. Push tag: `git push origin vX.Y.Z`
7. Create GitHub release

HACS will automatically detect new releases and notify users!

## Validation

Before publishing, validate locally:

```bash
# Install HACS action locally (requires act)
act -j validate

# Or manually check:
# - All files are present
# - manifest.json is valid JSON
# - Version numbers match
# - Tests pass
```

## Troubleshooting

### HACS Validation Fails

- Check `.github/workflows/validate.yaml` runs successfully
- Verify `hacs.json` is valid
- Ensure `manifest.json` has all required fields

### Integration Not Appearing

- Wait 30 minutes after release
- Clear HACS cache: Settings → HACS → ⋮ → Reload
- Check repository visibility (must be public)

### Version Mismatch

- Ensure `manifest.json` version matches git tag
- Tag format must be `vX.Y.Z` (with 'v' prefix)
- Manifest version must be `X.Y.Z` (without 'v')

## Resources

- [HACS Documentation](https://www.hacs.xyz/docs/publish/start/)
- [Integration Manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Semantic Versioning](https://semver.org/)

# Homebrew Formula for Pattern Renamer

This directory contains the Homebrew formula to distribute Pattern Renamer on
macOS.

## Installation

Create a tap repository

```bash
brew tap geoffreycoulaud/pattern-renamer
brew install pattern-renamer
```

## Maintenance Guide

### Testing the Formula

```bash
# Audit formula for style issues
brew audit pattern-renamer

# Test functionality
brew test pattern-renamer

# Test installation
brew install --HEAD pattern-renamer
```

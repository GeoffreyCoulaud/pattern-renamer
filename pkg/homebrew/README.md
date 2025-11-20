# Homebrew Formula for Pattern Renamer

This directory contains the Homebrew formula to distribute Pattern Renamer on
macOS.

## Installation

Users can install Pattern Renamer in several ways:

### Option 1: Direct Installation

```bash
brew install --HEAD --formula ./pkg/homebrew/pattern-renamer.rb
```

### Option 2: From Tap (Recommended for distribution)

Create a tap repository named `homebrew-pattern-renamer`:

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

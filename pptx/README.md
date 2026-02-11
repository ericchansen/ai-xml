# PowerPoint Generation

This folder contains tooling to generate the `AI-Workflow-Authoring.pptx` presentation from HTML slides.

## Prerequisites

```bash
cd pptx
npm install
```

## Usage

```bash
# Generate PowerPoint from HTML slides
node create-pptx.js
```

## Files

- `create-pptx.js` - Node.js script to convert HTML slides to PPTX
- `package.json` - Node.js dependencies (pptxgenjs)
- `slides/` - HTML source files for each slide (gitignored, generated)

## Notes

The HTML slide files in `slides/` are generated content and not tracked in git.
The final `AI-Workflow-Authoring.pptx` is kept in the repository root.

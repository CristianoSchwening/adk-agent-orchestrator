---
name: ai-elements CLI bug
description: Why the ai-elements CLI fails and what to do instead
---

The `npx ai-elements@latest add <component>` CLI (v1.9.0) always crashes with:
`ENOENT: no such file or directory, lstat '<project>/lib'`

It tries to resolve the `lib` alias from `components.json` as a bare path relative to the project root, ignoring the `@/` Vite alias and tsconfig paths. Even changing `"lib": "src/lib"` in `components.json` does not fix it.

**Why:** The CLI reads `components.json` aliases but resolves them with `lstat` before the Vite/TS alias is applied — it looks for `webapp-react/lib` literally.

**How to apply:** Build AI Elements-inspired components manually:
- Install Radix primitives: `@radix-ui/react-avatar`, `@radix-ui/react-hover-card`
- Install `class-variance-authority` for CVA variants
- Hand-write `Badge`, `Avatar`, `Button`, `HoverCard` shadcn-style components in `src/components/ui/`
- The resulting API is identical to what ai-elements would generate.

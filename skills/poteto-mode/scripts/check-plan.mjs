#!/usr/bin/env node
// Interim shim for #168: skills/poteto-mode/scripts/check-plan.mjs -> ../../../scripts/check-plan.mjs
// Keep root scripts/ canonical; this shim lives so skill_view serves it from any cwd.
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const rootScript = join(here, "../../../scripts/check-plan.mjs");
const { main } = await import(rootScript);
main(process.argv.slice(2));

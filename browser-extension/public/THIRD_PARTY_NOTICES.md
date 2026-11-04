# Third-party notices

SugarAgent packages the following open-source browser libraries locally. See the
corresponding files under `licenses/` for their complete license texts.

- Playwright extension relay and browser model — Microsoft Corporation, Apache-2.0.
  Source revision: e8149b8257d32dcf8f72573ecc43e72439da7080.
  https://github.com/microsoft/playwright
- React and React DOM — Meta Platforms, Inc. and affiliates, MIT.
- Marked — Christopher Jeffrey and contributors, MIT.
- DOMPurify — Cure53 and contributors, Apache-2.0 OR MPL-2.0.
- KaTeX — Khan Academy and contributors, MIT.
- Mermaid — Mermaid contributors, MIT.
- highlight.js — highlight.js contributors, BSD-3-Clause.

The extension relay's diagnostic logging is disabled and application heartbeat
responses are excluded from Chrome command dispatch. The host browser model
coalesces concurrent debugger attachment requests to handle global tab discovery.
Only import paths and the documented integration behaviour differ from the
vendored upstream bridge; page actions and model tool schemas remain upstream.

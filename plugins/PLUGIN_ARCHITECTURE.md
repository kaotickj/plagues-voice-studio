# Voice Studio plugin API 1

Plugins reside under `plugins/`. A `plugin.json` declares id, name, version,
api_version=1 and a Python entry_point inside its folder. Discovery reads only
manifests. Selecting **Plugins → name** imports the entry point in a unique
package namespace; relative imports stay isolated between plugins.

The factory `create_plugin(context)` returns a QWidget exposing a boolean
`is_busy` property and a `cancel()` method. The host owns a single reusable,
nonmodal dialog per plugin. A busy close requests cancellation and keeps the
panel alive until its worker stops. Host shutdown refuses to destroy an active
worker. Plugin code inherits the host theme and must not restyle QApplication.

The context contains the host parent, a stable per-plugin data directory,
`can_generate()` (empty string means available, otherwise a user-facing reason),
and `handoff(text)` returning whether reviewed text was accepted. The writer
requires review before calling handoff; Voice Studio confirms replacement of a
nonempty script, selects Narration Studio, and does not start speech generation.
The main narrator, optional-engine operations and Model Manager defer while a
plugin is working. The writer also defers to active host operations.

## Generic and standalone writing products

`writer_core` contains shared model/runtime downloads, settings validation,
setup UI, the owned loopback-authenticated llama.cpp server and memory recovery.
The runtime exposes `generate_messages`; each product supplies its own prompts.

The promotional plugin provides generic copywriting recipes and explicit brief
fields. It does not import DJ Writer, lore, stations, speech tags or radio story
planning. It can read existing runtime/model preferences once without copying
weights or changing the old setup. Its own saved settings remain independent.

The branded DJ standalone derives its local writer from the same runtime while
retaining DJ-specific prompts, profiles, internal story planning and editorial
checks. Its PyInstaller spec bundles the shared package separately. Voice Studio's
spec includes the generic writer, Script Prep and shared runtime, excluding DJ assets,
models, EXEs, tests and build environments.

Pronunciation & Script Prep uses the same API 1 factory and reviewed handoff,
with atomic per-plugin dictionaries. It runs synchronously with bounded text
and no model, thread or engine markup. Its load-script action reads the current
host editor; preparation never changes that editor until explicit handoff.

Source launches inspect the checkout's `plugins/`; frozen builds inspect bundled
`_internal/plugins/` and optional `plugins/` beside the EXE. An external plugin
with the same id overrides the bundled manifest on the next host start. Native
code and Python plugins are trusted installed code; this is not a code sandbox.
Do not install plugin code from untrusted sources. API mismatches and invalid
entry-point paths are shown in Plugins → Plugin loading details.

## DLLs

A native DLL is possible with a deliberately defined ABI/lifecycle contract, or
Qt's native plugin interface. A `.pyd` is a Python-specific DLL requiring a
compatible runtime. Renaming an EXE does not create a plugin. This implementation
uses Python/QWidget factories; no native DLL is needed or produced. Existing
Voice Studio EXEs still require rebuilding to gain plugin API 1.

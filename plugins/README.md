# Voice Studio plugins

Plugin source lives here. Voice Studio discovers API-1 `plugin.json` manifests
and opens panels through its **Plugins** menu. The main Windows distribution
ships only `promotional-writer/` plus its `writer_core` dependency.

- `promotional-writer/`: generic local ad copy, promos, announcements, product
  descriptions, social posts, taglines and custom prompts. No DJ/Fallout defaults.
- `writer_core/`: shared verified downloads, runtime configuration, model setup,
  owned llama.cpp process and memory recovery. No product-specific prompts.
- `dj-writer/`: the separate Goodneighbor / Plague Radio standalone. Its branding,
  profiles and story recipes are not included in the generic plugin or host.

The generic plugin can reuse existing model/runtime paths without copying weights
or importing DJ profiles. Settings live in Voice Studio's stable data folder
under `plugins/promotional-writer/`. See each package README and
[PLUGIN_ARCHITECTURE.md](PLUGIN_ARCHITECTURE.md) for integration details.

Build the generic source-plugin ZIP:

```powershell
python plugins/promotional-writer/build_plugin.py
```

Build the separate branded standalone:

```powershell
./plugins/dj-writer/build_windows.ps1
```

Both have dedicated Actions workflows. The main Voice Studio workflow includes
changes to the generic plugin and shared runtime. No weights are shipped by
these plugin packages. Existing frozen hosts need rebuilding to gain the loader.

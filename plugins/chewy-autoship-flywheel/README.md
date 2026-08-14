# Chewy — Autoship Subscription Flywheel (Sigma plugin)

Bespoke hero plugin for the Chewy "Pet Commerce & Autoship Command Center"
workbook. Renders a flywheel donut of net sales by business line with the
Autoship penetration in the hub. Binds to the product-card table
(`product` / `value` / `members` / `goal`); ships a `synth()` fallback so it
renders unbound.

## Hosting

Sigma loads a plugin by URL and needs it served as `text/html`. Enable GitHub
Pages on this repo (Settings → Pages → Source = the branch holding this file,
root), then the plugin is reachable at:

```
https://patrickmurphy17.github.io/myblankrepo/plugins/chewy-autoship-flywheel/index.html
```

Register it once via `POST /v2/plugins` and reference the returned `pluginId`
from the workbook's hero slot. (jsDelivr is not usable here: it serves `.html`
as `text/plain`, which breaks both first-paint and PNG export.)

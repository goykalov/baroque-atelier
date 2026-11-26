# Barocco Atelier showcase

## Carved halls

Ten views of three locally generated interiors inside a **12 × 8.5 × 6.8 m** room. The white studies show the depth of the relief. The colour studies use sage, blue-grey, limestone and muted clay finishes. The images are Blender Cycles views with an ImageGen pass for lighting and materials.

| White plaster | Mineral colours |
| --- | --- |
| [![Window light in an interlaced hall](showcase/carved/01-white-window-light.jpg)](showcase/carved/01-white-window-light.jpg) | [![Muted sage in the interlaced hall](showcase/carved/06-color-muted-sage.jpg)](showcase/carved/06-color-muted-sage.jpg) |
| [![White plaster on a ribbed vault](showcase/carved/02-white-plaster-salon.jpg)](showcase/carved/02-white-plaster-salon.jpg) | [![Blue-grey on the ribbed vault](showcase/carved/07-color-blue-gray.jpg)](showcase/carved/07-color-blue-gray.jpg) |
| [![Close view of white plaster acanthus](showcase/carved/03-white-carved-detail.jpg)](showcase/carved/03-white-carved-detail.jpg) | [![Close view of limestone-toned relief](showcase/carved/08-color-limestone-detail.jpg)](showcase/carved/08-color-limestone-detail.jpg) |
| [![Woven vault under overcast light](showcase/carved/04-white-overcast.jpg)](showcase/carved/04-white-overcast.jpg) | [![Woven vault in muted clay](showcase/carved/09-color-muted-clay.jpg)](showcase/carved/09-color-muted-clay.jpg) |
| [![White ceiling seen straight up](showcase/carved/05-white-ceiling.jpg)](showcase/carved/05-white-ceiling.jpg) | [![Mineral green ceiling seen straight up](showcase/carved/10-color-mineral-ceiling.jpg)](showcase/carved/10-color-mineral-ceiling.jpg) |

Open a generation recipe in the Windows app and click **Пересобрать рецепт** to rebuild the hall. [Interlaced arcade](../examples/carved/interlaced-arcade.recipe.json) · [Ribbed vault](../examples/carved/ribbed-vault.recipe.json) · [Woven vault](../examples/carved/woven-vault.recipe.json)

## Earlier halls

Six local searches used the same **12 × 8.5 × 6.8 m** room envelope. The gallery compares different wall structures and ceiling compositions. Each image starts from the exported 3D geometry rendered in Blender Cycles, then uses the same ImageGen finishing direction for window light, mineral plaster, aged gilding and wood grain.

### 01 · Upper gallery and radial tracery

![Upper gallery and radial tracery](showcase/hall-03.jpg)

[Editable generation recipe](../examples/gallery/hall-03.recipe.json)

### 02 · Arcades and interlaced vault

![Arcades and interlaced vault](showcase/hall-04.jpg)

[Editable generation recipe](../examples/gallery/hall-04.recipe.json)

### 03 · Paired columns and scalloped relief

![Paired columns and scalloped relief](showcase/hall-05.jpg)

[Editable generation recipe](../examples/gallery/hall-05.recipe.json)

### 04 · Exedras and deep coffers

![Exedras and deep coffers](showcase/hall-06.jpg)

[Editable generation recipe](../examples/gallery/hall-06.recipe.json)

### 05 · Paired columns and ribbed vault

![Paired columns and ribbed vault](showcase/hall-07.jpg)

[Editable generation recipe](../examples/gallery/hall-07.recipe.json)

### 06 · Exedras and garlands

![Exedras and garlands](showcase/hall-08.jpg)

[Editable generation recipe](../examples/gallery/hall-08.recipe.json)

The [generation log](../examples/gallery/gallery.json) records the briefs, selected wall and ceiling structures, seeds, search passes, and original OBJ hashes. The two original preview scenes are available as OBJ downloads in the [v0.1.0 release](https://github.com/goykalov/baroque-atelier/releases/tag/v0.1.0).

## v0.2.0 · Ceiling revision

A local search with the 10-minute preset finished in 3 minutes 17 seconds. It compared 95 valid recipes and accepted 15 Qwen proposals. A second search rebuilt the ceiling with a central relief and open corners inside the same hall. Window light and material textures were finished in ImageGen over the Blender render.

![The revised baroque ceiling with the original arcaded walls](showcase/v0.2.0-ceiling.jpg)

[Starting hall recipe](../examples/v0.2.0/before.recipe.json) · [Ceiling revision recipe](../examples/v0.2.0/after.recipe.json)

## v0.3.0 · One hall across three budgets

The three presets share the same composition and room dimensions. The medium preset adds three refinement stages. The hour preset adds six, including a second series of frames, friezes and sculpture groups. These are matched Blender views of the exported geometry.

![One hall across the 1-minute, 10-minute and 1-hour presets](showcase/v0.3.0-quality.jpg)

[Generation comparison](../examples/v0.3.0/comparison.json) · [Fast recipe](../examples/v0.3.0/fast.recipe.json) · [Medium recipe](../examples/v0.3.0/medium.recipe.json) · [Hour recipe](../examples/v0.3.0/hour.recipe.json)

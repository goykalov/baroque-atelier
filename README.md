# Baroque Atelier

[![BAROCCO ATELIER](docs/showcase/cover.png)](docs/SHOWCASE.md)

**Baroque Atelier is a local design tool for exploring baroque interiors inside a fixed room envelope.** Generate a hall with a blank brief or describe a direction, then tune the relief, branching, and room dimensions in Grasshopper. The desktop edition exports editable OBJ meshes, materials, and a JSON recipe.

[Русская инструкция](docs/README.ru.md) · [Showcase and project files](docs/SHOWCASE.md) · [Artwork and dependencies](docs/ATTRIBUTION.md)

## Try the preview

1. [Download the current project as a ZIP](https://github.com/goykalov/baroque-atelier/archive/refs/heads/main.zip) and extract it.
2. In Rhino 9, open [Atelier-Carved.gh](atelier/Atelier-Carved.gh) in Grasshopper. For the standalone Windows interface, launch **atelier/Start Atelier.cmd** with Python 3.9+ and Tcl/Tk installed.
3. Select **Автономные правила** (local rules), choose a search preset and click **Найти новый зал** (find a new hall). A blank brief is enough. The interface uses Russian.

For offline Qwen search, copy the **atelier/engine** folder from the [v0.3.0 Windows release](https://github.com/goykalov/baroque-atelier/releases/tag/v0.3.0) into the current project or point **BAROQUE_LLAMA_BIN** to a local **llama-completion.exe**. Put [Qwen3 8B GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF) at **atelier/models/qwen3-8b.gguf** or set **BAROQUE_MODEL_PATH**. The tool can also open existing Ollama **qwen3:8b** weights directly in llama.cpp. Then select **Qwen без сети** (offline Qwen).

## Carved hall

The new mode builds branching plaster relief across the ceiling, walls, friezes, and dado. Acanthus grows out of the panel mouldings. The **Влияние формулы, %** slider changes how strongly recursive branching and interlacing shape the relief. The new mode uses plaster and wood finishes without gilding.

## What you can control

- Room length, width, and height, or a rectangular closed room volume in Grasshopper.
- A new combination of wall structure, bay count, wall cross-section, ceiling volume, and field layout at each search. The search compares recent architecture and spatial layouts.
- Ornament depth, foliage, branching, and optional museum paintings as ceiling textures. The classic mode also offers a gilding control.
- Quick composition search, three or six refinement stages, and experimental **5- or 60-minute volume searches** that compare vault geometries and ceiling layouts. Use **Сохранить найденное** to finish with the best result so far. Preparation and final export add to the volume search time.
- Prompt-driven edits to the **ceiling** or **relief above the door**. Choose a zone and click **Применить правку**. The other parts keep their geometry. In Rhino, matching parts also keep their object IDs.

In the Windows app, open a saved recipe before editing. The current project supplies the dimensions and mesh settings for zone edits. During a search, the exporter saves a recoverable `.checkpoint.json` beside the target OBJ and removes it after a successful export.

## Gallery

Ten studies of three carved halls at the same **12 × 8.5 × 6.8 m** dimensions. The white series shows the relief in plaster. The colour series explores restrained mineral finishes. Blender Cycles renders of the local geometry were used as the source for lighting and material finishing in ImageGen. [Full-size views and generation recipes](docs/SHOWCASE.md)

[![Carved plaster hall with daylight across the walls and parquet](docs/showcase/carved/02-white-plaster-salon.jpg)](docs/SHOWCASE.md)

## Project status

This is a Windows and Rhino 9 design preview. The output is polygonal concept geometry. The main carved hall has about 10.7 million triangles at its gallery settings. The original project code currently has no open-source license specified. The museum assets and third-party runtime have separate terms. [Attribution](docs/ATTRIBUTION.md)

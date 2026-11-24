# Baroque Atelier

[![Six generated baroque halls](docs/showcase/cover.jpg)](docs/SHOWCASE.md)

**Baroque Atelier is a local design tool for exploring baroque interiors inside a fixed room envelope.** Generate a hall with a blank brief or describe a direction, then tune the relief, branching, and room dimensions in Grasshopper. The desktop edition exports editable OBJ meshes, materials, and a JSON recipe.

[Русская инструкция](docs/README.ru.md) · [Showcase and project files](docs/SHOWCASE.md) · [Artwork and dependencies](docs/ATTRIBUTION.md)

## Try the preview

1. Download **baroque-atelier-v0.3.0-windows.zip** from the [v0.3.0 release](https://github.com/goykalov/baroque-atelier/releases/tag/v0.3.0) and extract it.
2. Launch **atelier/Start Atelier.cmd** for the standalone Windows interface. It uses Python 3.9+ with Tcl/Tk. For Rhino 9, open **atelier/Atelier.gh** in Grasshopper.
3. Select a search budget and click **Найти новый зал**. A blank brief is enough. The interface currently uses Russian.

The Windows archive includes llama.cpp. For offline Qwen search, place **Qwen3 8B GGUF** at **atelier/models/qwen3-8b.gguf** or set **BAROQUE_MODEL_PATH**. The tool can also find an existing Ollama **qwen3:8b** weight file and open it directly in llama.cpp. The standalone **Автономные правила** mode works without model weights. [Qwen3 8B GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF)

## What you can control

- Room length, width, and height, or a rectangular closed room volume in Grasshopper.
- A new combination of wall structure, bay count, wall cross-section, ceiling volume, and field layout at each search. The search compares recent architecture and spatial layouts.
- Recursive acanthus relief, ornament depth, foliage, gilding, and museum paintings placed as ceiling textures.
- Three generation budgets. **1 minute** selects the base composition. **10 minutes** can add carved ceiling accents, dado panels, and sculpture brackets. **1 hour** can add a second series of carved frames, friezes, and sculpture groups over the same room. The budgets are upper limits. Use **Сохранить найденное** to finish with the completed stages.
- Prompt-driven edits to the **ceiling** or **relief above the door**. Choose a zone and click **Применить правку**. The other parts keep their geometry. In Rhino, matching parts also keep their object IDs.

In the Windows app, open a saved recipe before editing. The current project supplies the dimensions and mesh settings for zone edits. During a search, the exporter saves a recoverable `.checkpoint.json` beside the target OBJ and removes it after a successful export.

## Gallery

Six halls generated locally at the same **12 × 8.5 × 6.8 m** dimensions. Each frame starts from exported 3D geometry rendered in Blender Cycles, with photographic finishing in ImageGen. [Full-size views and generation recipes](docs/SHOWCASE.md)

## Project status

This is a Windows and Rhino 9 design preview. The output is polygonal concept geometry. All three presets were exercised with local Qwen. Detailed exports can be large. The original project code currently has no open-source license specified. The museum assets and third-party runtime have separate terms. [Attribution](docs/ATTRIBUTION.md)

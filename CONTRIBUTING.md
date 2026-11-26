# Contributing to Barocco Atelier

English and Russian are both welcome. Post hall studies, style references and questions in [Discussions](https://github.com/goykalov/baroque-atelier/discussions). Use [Issues](https://github.com/goykalov/baroque-atelier/issues) when there is a reproducible problem or a concrete change to implement.

## Share a reproducible example

- Include the project revision, Rhino or Python version, and whether you used Grasshopper or the Windows app.
- Attach the generation recipe if you can share it. Include dimensions, seed, search preset, backend and the formula influence setting when they matter.
- Describe the steps and the result you expected. For a geometry issue, a marked-up viewport capture or section makes the failure easier to find.
- Remove private project data and local paths from attachments before posting.

## Submit a change

Link the relevant issue in your pull request and say how you verified the change. For changes to geometry, include the recipe and before-and-after views at the same camera and lighting where possible. Link to source artwork and its license for any third-party asset.

Run the existing generation checks from the repository root.

```powershell
python -m unittest discover -s tests -v
```

[Roadmap](ROADMAP.md) · [Attribution](docs/ATTRIBUTION.md)
